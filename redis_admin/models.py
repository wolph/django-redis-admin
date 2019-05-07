import collections
import json
import logging

import base64
import typing
import binascii

import redis
from django.db import models
from django.utils import timezone

from . import settings


logger = logging.getLogger(__name__)


def decode_bytes(value, encoding='utf-8', method='replace'):
    if isinstance(value, bytes):
        return value.decode(encoding, method)
    else:
        return value


class RedisMeta:
    managed = False

    def get_field(self, name):
        class Field:
            is_relation = False
            auto_created = True

        return Field()

    def __getattr__(self, key):
        message = 'meta.%s' % key
        print(message)
        raise AttributeError('Unknown attribute %s' % message)


class RedisValue(models.Model):

    TYPES = dict()

    key = models.CharField(max_length=256, primary_key=True)
    raw_value = models.TextField()
    type = models.CharField(max_length=8)
    expires_at = models.DateTimeField(null=True, blank=True)
    idle_since = models.DateTimeField(null=True, blank=True)
    base64 = models.BooleanField()
    json = models.BooleanField()

    @classmethod
    def register_type(cls, type):
        def _register_type(class_):
            cls.TYPES[type] = class_
            return class_

        return _register_type

    @classmethod
    def create(cls, type, **kwargs):
        class_ = cls.TYPES.get(type, cls)
        return class_(type=type, **kwargs)

    def decode_string(self, raw_value):
        v0 = raw_value
        raw_value = decode_bytes(raw_value) or ''

        v1 = raw_value
        if settings.BASE64_KEY_RE.match(self.key):
            try:
                raw_value = decode_bytes(base64.b64decode(raw_value))
                self.base64 = True
            except binascii.Error:
                self.base64 = False

        v2 = raw_value
        if settings.JSON_KEY_RE.match(self.key):
            try:
                raw_value = settings.JSON_MODULE.loads(raw_value)
                self.json = True
            except json.JSONDecodeError as e:
                print('error %r attempting json on: %r', e, raw_value)
                self.json = False

        return raw_value

    @property
    def value(self):
        print('calling value', self.type, self.raw_value)
        return self.raw_value

    @property
    def ttl(self):
        if self.expires_at:
            return self.expires_at - timezone.now()

    @property
    def idle(self):
        if self.idle_since:
            return timezone.now() - self.idle_since

    @property
    def cropped_value(self):
        return self.get_cropped_value(settings.CROP_SIZE)

    def get_cropped_value(self, crop_size):
        value = str(self.value)

        if len(value) >= crop_size:
            crop_half = crop_size // 2
            value = value[:crop_half] + '...' + value[-crop_half:]
        return value

    def fetch_value(self, client: redis.Redis):
        '''
        Fetch the value. Note that if a pipe is passed as `client` the
        result will be in the `pipe.execute()` instead
        '''
        raise NotImplementedError('fetch_value is not implemented for %r'
                                  % self.type)

    def __getattr__(self, key):
        message = '%s.%s' % (self.__class__.__name__, key)
        print(message)
        raise AttributeError('Unknown attribute %s' % message)

    def __repr__(self):
        return '<{class_name}[{key}] {value}>'.format(
            class_name=self.__class__.__name__,
            key=self.key,
            value=self.get_cropped_value(40),
        )

    class Meta(RedisMeta):
        abstract = True


@RedisValue.register_type('string')
class RedisString(RedisValue):

    def fetch_value(self, client: redis.Redis):
        return client.get(self.key)

    @property
    def value(self):
        return self.decode_string(self.raw_value)


@RedisValue.register_type('list')
class RedisList(RedisValue):

    def fetch_value(self, client: redis.Redis):
        return client.lrange(self.key, 0, -1)

    @property
    def value(self) -> typing.List:
        raw_value = self.raw_value
        if raw_value:
            raw_value = [self.decode_string(v) for v in raw_value]

        return raw_value


@RedisValue.register_type('set')
class RedisSet(RedisList):

    def fetch_value(self, client: redis.Redis):
        return client.smembers(self.key)

    @property
    def value(self) -> typing.List:
        return set(RedisList.value(self))


@RedisValue.register_type('hash')
class RedisHash(RedisValue):

    def fetch_value(self, client: redis.Redis):
        return client.hgetall(self.key)

    @property
    def value(self) -> typing.Mapping:
        raw_value = self.raw_value
        if raw_value:
            raw_value = {decode_bytes(k): self.decode_string(v)
                         for k, v in raw_value.items()}

        return raw_value


@RedisValue.register_type('zset')
class RedisZSet(RedisHash):

    def fetch_value(self, client: redis.Redis):
        return client.zrangebyscore(self.key, '-inf', '+inf', withscores=True)

    @property
    def value(self) -> collections.OrderedDict:
        raw_value = self.raw_value
        if raw_value:
            raw_value = collections.OrderedDict(
                (decode_bytes(k), self.decode_string(v))
                for k, v in raw_value)

        return raw_value


server_models = dict()

for name, server in settings.SERVERS.items():
    class Meta(RedisMeta):
        pass

    # Overwrite meta variables if available
    if 'meta' in server:
        for key, value in server['meta'].items():
            setattr(Meta, key, value)

    server_models[name] = type(name.capitalize(), (RedisValue,), {
        '__module__': __name__,
        'Meta': Meta,
    })
    globals()[name.capitalize()] = server_models[name]

