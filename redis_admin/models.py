import base64
import binascii
import collections
import json
import logging
import typing

import redis
from django.db import models
from django.utils import timezone

from . import settings

logger: logging.Logger = logging.getLogger(__name__)


def decode_bytes(
    value: typing.Any, encoding: str = 'utf-8', method: str = 'replace'
) -> typing.Any:
    if isinstance(value, bytes):
        return value.decode(encoding, method)
    return value


class RedisMeta:
    managed: bool = False
    exclude_key_prefixes: tuple[str, ...] | None = None
    exclude_key_re: typing.Pattern | None = None
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
    TYPES: typing.ClassVar[dict[str, type]] = {}

    key = models.CharField(max_length=256, primary_key=True)
    raw_value = models.TextField()
    type = models.CharField(max_length=8)
    expires_at = models.DateTimeField(null=True, blank=True)
    idle_since = models.DateTimeField(null=True, blank=True)
    base64 = models.BooleanField()
    json = models.BooleanField()

    @classmethod
    def register_type(
        cls, type: str
    ) -> typing.Callable[[typing.Any], typing.Any]:
        def _register_type(class_: typing.Any) -> typing.Any:
            cls.TYPES[type] = class_
            return class_

        return _register_type

    @classmethod
    def create(cls, type: str, **kwargs: typing.Any) -> typing.Any:
        class_: typing.Any = cls.TYPES.get(type, cls)
        return class_(type=type, **kwargs)

    def decode_string(self, raw_value: typing.Any) -> typing.Any:
        raw_value = decode_bytes(raw_value) or ''

        if settings.BASE64_KEY_RE.match(self.key):
            try:
                raw_value = decode_bytes(base64.b64decode(raw_value))
                self.base64 = True
            except binascii.Error:
                self.base64 = False

        if settings.JSON_KEY_RE.match(self.key):
            try:
                raw_value = settings.JSON_MODULE.loads(raw_value)
                self.json = True
            except json.JSONDecodeError as e:
                logger.debug('error %r attempting json on: %r', e, raw_value)
                self.json = False

        return raw_value

    @property
    def value(self) -> typing.Any:
        return self.raw_value

    @property
    def ttl(self) -> typing.Any:
        if self.expires_at:
            return self.expires_at - timezone.now()
        return None

    @property
    def idle(self) -> typing.Any:
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

    def fetch_value(self, client: redis.Redis) -> typing.Any:
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
    def fetch_value(self, client: redis.Redis) -> typing.Any:
        return client.get(self.key)

    @property
    def value(self) -> typing.Any:
        return self.decode_string(self.raw_value)


@RedisValue.register_type('list')
class RedisList(RedisValue):
    def fetch_value(self, client: redis.Redis) -> typing.Any:
        return client.lrange(self.key, 0, -1)

    @property
    def value(self) -> list[typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            raw_value = [self.decode_string(v) for v in raw_value]

        return raw_value


@RedisValue.register_type('set')
class RedisSet(RedisList):
    def fetch_value(self, client: redis.Redis) -> typing.Any:
        return client.smembers(self.key)

    @property
    def value(self) -> set[typing.Any]:
        return set(super().value)


@RedisValue.register_type('hash')
class RedisHash(RedisValue):
    def fetch_value(self, client: redis.Redis) -> typing.Any:
        return client.hgetall(self.key)

    @property
    def value(self) -> typing.Mapping[typing.Any, typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            raw_value = {
                decode_bytes(k): self.decode_string(v)
                for k, v in raw_value.items()
            }

        return raw_value


@RedisValue.register_type('zset')
class RedisZSet(RedisHash):
    def fetch_value(self, client: redis.Redis) -> typing.Any:
        return client.zrangebyscore(self.key, '-inf', '+inf', withscores=True)

    @property
    def value(self) -> collections.OrderedDict[typing.Any, typing.Any]:
        raw_value: typing.Any = self.raw_value
        if raw_value:
            raw_value = collections.OrderedDict(
                (decode_bytes(k), self.decode_string(v)) for k, v in raw_value
            )

        return raw_value


server_models: dict[str, type] = {}

for name, server in settings.SERVERS.items():

    class Meta(RedisMeta):
        pass

    # Overwrite meta variables if available
    if 'meta' in server:
        for key, value in server['meta'].items():
            setattr(Meta, key, value)

    for exclude_attr in (
        'exclude_key_prefixes',
        'exclude_key_re',
        'exclude_keys',
    ):
        if exclude_attr in server:
            setattr(Meta, exclude_attr, server[exclude_attr])

    server_models[name] = type(
        name.capitalize(),
        (RedisValue,),
        {
            '__module__': __name__,
            'Meta': Meta,
        },
    )
    globals()[name.capitalize()] = server_models[name]
