# pyright: reportPrivateUsage=false
from __future__ import annotations

import base64
import binascii
import builtins
import collections
import json
import logging
import re
import typing
from datetime import datetime, timedelta

import redis
from django.db import models
from django.utils import timezone
from typing_extensions import override

from . import settings

logger: logging.Logger = logging.getLogger(__name__)


T = typing.TypeVar('T')
R = typing.TypeVar('R', bound='RedisValue')


@typing.overload
def decode_bytes(
    value: bytes, encoding: str = 'utf-8', method: str = 'replace'
) -> str: ...


@typing.overload
def decode_bytes(
    value: T, encoding: str = 'utf-8', method: str = 'replace'
) -> T: ...


def decode_bytes(
    value: typing.Any, encoding: str = 'utf-8', method: str = 'replace'
) -> typing.Any:
    if isinstance(value, bytes):
        return value.decode(encoding, method)
    return value


class RedisMeta:
    managed: bool = False
    exclude_key_prefixes: tuple[str, ...] | None = None
    exclude_key_re: re.Pattern[str] | None = None
    exclude_keys: set[str] | None = None

    def get_field(self, name: str) -> typing.Any:
        class Field:
            is_relation: bool = False
            auto_created: bool = True

        return Field()

    def __getattr__(self, key: str) -> typing.Any:
        message: str = f'meta.{key}'
        raise AttributeError(f'Unknown attribute {message}')


class RedisValue(models.Model):
    if typing.TYPE_CHECKING:
        _meta: typing.ClassVar[typing.Any]

    TYPES: typing.ClassVar[dict[str, builtins.type[RedisValue]]] = {}

    key: models.CharField[str, str] = models.CharField(
        max_length=256, primary_key=True
    )
    raw_value: models.TextField[typing.Any, typing.Any] = models.TextField()
    type: models.CharField[str, str] = models.CharField(max_length=8)
    expires_at: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    idle_since: models.DateTimeField[datetime | None, datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    base64: models.BooleanField[bool, bool] = models.BooleanField()
    json: models.BooleanField[bool, bool] = models.BooleanField()

    @classmethod
    def register_type(
        cls, type: str
    ) -> typing.Callable[[builtins.type[R]], builtins.type[R]]:
        def _register_type(class_: builtins.type[R]) -> builtins.type[R]:
            cls.TYPES[type] = class_
            return class_

        return _register_type

    @classmethod
    def create(cls, type: str, **kwargs: typing.Any) -> RedisValue:
        class_: builtins.type[RedisValue] = cls.TYPES.get(type, cls)
        instance: RedisValue = class_(type=type, **kwargs)
        return instance

    def decode_string(self, raw_value: typing.Any) -> typing.Any:
        decoded: typing.Any = decode_bytes(raw_value) or ''

        if settings.BASE64_KEY_RE.match(self.key):
            try:
                decoded = decode_bytes(base64.b64decode(decoded))
                self.base64 = True
            except binascii.Error:
                self.base64 = False

        if settings.JSON_KEY_RE.match(self.key):
            try:
                decoded = settings.JSON_MODULE.loads(decoded)
                self.json = True
            except json.JSONDecodeError as e:
                logger.debug('error %r attempting json on: %r', e, decoded)
                self.json = False

        return decoded

    @property
    def value(self) -> typing.Any:
        return self.raw_value

    @property
    def ttl(self) -> timedelta | None:
        if self.expires_at:
            return self.expires_at - timezone.now()
        return None

    @property
    def idle(self) -> timedelta | None:
        if self.idle_since:
            return timezone.now() - self.idle_since
        return None

    @property
    def cropped_value(self) -> str:
        return self.get_cropped_value(settings.CROP_SIZE)

    def get_cropped_value(self, crop_size: int) -> str:
        value: str = str(self.value)

        if len(value) >= crop_size:
            crop_half: int = crop_size // 2
            value = value[:crop_half] + '...' + value[-crop_half:]
        return value

    def fetch_value(self, client: redis.Redis[bytes]) -> typing.Any:
        """Fetch the value.

        Note that if a pipe is passed as `client` the result will be in the
        `pipe.execute()` instead.
        """
        raise NotImplementedError(
            f'fetch_value is not implemented for {self.type!r}'
        )

    def __getattr__(self, key: str) -> typing.Any:
        message: str = f'{self.__class__.__name__}.{key}'
        raise AttributeError(f'Unknown attribute {message}')

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__}[{self.key}] '
            f'{self.get_cropped_value(40)}>'
        )

    class Meta(RedisMeta):
        abstract = True


@RedisValue.register_type('string')
class RedisString(RedisValue):
    @override
    def fetch_value(self, client: redis.Redis[bytes]) -> typing.Any:
        return client.get(self.key)

    @property
    @override
    def value(self) -> typing.Any:
        return self.decode_string(self.raw_value)


@RedisValue.register_type('list')
class RedisList(RedisValue):
    @override
    def fetch_value(self, client: redis.Redis[bytes]) -> typing.Any:
        return client.lrange(self.key, 0, -1)

    @property
    @override
    def value(self) -> list[typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            return [self.decode_string(v) for v in raw_value]
        return []


@RedisValue.register_type('set')
class RedisSet(RedisValue):
    @override
    def fetch_value(self, client: redis.Redis[bytes]) -> typing.Any:
        return client.smembers(self.key)

    @property
    @override
    def value(self) -> set[typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            return {self.decode_string(v) for v in raw_value}
        return set()


@RedisValue.register_type('hash')
class RedisHash(RedisValue):
    @override
    def fetch_value(self, client: redis.Redis[bytes]) -> typing.Any:
        return client.hgetall(self.key)

    @property
    @override
    def value(self) -> typing.Mapping[typing.Any, typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            return {
                decode_bytes(k): self.decode_string(v)
                for k, v in raw_value.items()
            }
        return {}


@RedisValue.register_type('zset')
class RedisZSet(RedisHash):
    @override
    def fetch_value(self, client: redis.Redis[bytes]) -> typing.Any:
        return client.zrangebyscore(self.key, '-inf', '+inf', withscores=True)

    @property
    @override
    def value(self) -> collections.OrderedDict[typing.Any, typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            return collections.OrderedDict(
                (decode_bytes(k), self.decode_string(v)) for k, v in raw_value
            )
        return collections.OrderedDict()


server_models: dict[str, type[RedisValue]] = {}

for name, server in settings.SERVERS.items():

    class Meta(RedisMeta):
        pass

    # Overwrite meta variables if available
    if 'meta' in server:
        for key, value in server['meta'].items():
            setattr(Meta, key, value)

    model_class: type[RedisValue] = type(
        name.capitalize(),
        (RedisValue,),
        {
            '__module__': __name__,
            'Meta': Meta,
        },
    )
    server_models[name] = model_class

    model_meta: typing.Any = model_class._meta
    if 'meta' in server:
        for key, value in server['meta'].items():
            setattr(model_meta, key, value)

    for exclude_attr in (
        'exclude_key_prefixes',
        'exclude_key_re',
        'exclude_keys',
    ):
        if exclude_attr in server:
            setattr(model_meta, exclude_attr, server[exclude_attr])

    globals()[name.capitalize()] = model_class

if typing.TYPE_CHECKING:

    class Default(RedisValue):
        _meta: typing.ClassVar[typing.Any]
