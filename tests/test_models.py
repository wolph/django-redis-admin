# pyright: reportPrivateUsage=false
from __future__ import annotations

import base64
import collections
import importlib
import re
import typing
from datetime import timedelta
from unittest import mock

import pytest
import redis
from django.utils import timezone

from redis_admin import (
    __about__,
    models,
    settings as redis_settings,
)


def test_about() -> None:
    assert __about__.__title__ == 'Django Redis Admin'
    assert __about__.__package_name__ == 'django-redis-admin'
    assert 'Rick van Hattem' in __about__.__author__
    assert 'Django Admin interface' in __about__.__description__
    assert __about__.__email__ == 'wolph@wol.ph'
    assert __about__.__version__ == '0.3.0'
    assert __about__.__license__ == 'BSD'
    assert 'Rick van Hattem' in __about__.__copyright__
    assert 'github.com' in __about__.__url__


def test_settings_exclude_helpers() -> None:
    assert redis_settings.get_exclude_key_prefixes(None) == ()
    assert redis_settings.get_exclude_key_prefixes('') == ()
    assert redis_settings.get_exclude_key_prefixes('single:') == ('single:',)
    expected_prefixes: tuple[str, ...] = ('a:', 'b:')
    assert (
        redis_settings.get_exclude_key_prefixes(['a:', 'b:'])
        == expected_prefixes
    )

    assert redis_settings.get_exclude_key_re(None) is None
    assert redis_settings.get_exclude_key_re('') is None
    compiled_str: re.Pattern[str] | None = redis_settings.get_exclude_key_re(
        '^test:'
    )
    assert compiled_str is not None
    assert compiled_str.pattern == '^test:'

    pattern_obj: re.Pattern[str] = re.compile('^pattern:')
    assert redis_settings.get_exclude_key_re(pattern_obj) is pattern_obj
    assert redis_settings.get_exclude_key_re(12345) is None

    assert redis_settings.get_exclude_keys(None) == set()
    assert redis_settings.get_exclude_keys('') == set()
    assert redis_settings.get_exclude_keys('single_key') == {'single_key'}
    assert redis_settings.get_exclude_keys(['k1', 'k2']) == {'k1', 'k2'}


def test_decode_bytes() -> None:
    assert models.decode_bytes(b'hello') == 'hello'
    assert models.decode_bytes('already_str') == 'already_str'
    assert models.decode_bytes(123) == 123
    assert models.decode_bytes(None) is None

    decoded_custom: str = models.decode_bytes(
        b'\xff', encoding='ascii', method='ignore'
    )
    assert decoded_custom == ''


def test_redis_meta() -> None:
    meta: models.RedisMeta = models.RedisMeta()
    field: typing.Any = meta.get_field('any_field')
    assert field.is_relation is False
    assert field.auto_created is True

    with pytest.raises(
        AttributeError, match=r'Unknown attribute meta\.nonexistent'
    ):
        _ = meta.nonexistent


def test_redis_value_register_and_create() -> None:
    class CustomType(models.Default):
        class Meta(models.RedisValue.Meta):
            proxy = True
            app_label = 'redis_admin'

    models.RedisValue.register_type('test_custom_type')(CustomType)

    assert models.RedisValue.TYPES.get('test_custom_type') is CustomType

    instance: models.RedisValue = models.Default.create(
        'test_custom_type', key='k1'
    )
    assert isinstance(instance, CustomType)
    assert instance.type == 'test_custom_type'
    assert instance.key == 'k1'

    fallback: models.RedisValue = models.Default.create(
        'unregistered_type', key='k2'
    )
    assert type(fallback) is models.Default
    assert fallback.type == 'unregistered_type'
    assert fallback.key == 'k2'

    models.RedisValue.TYPES.pop('test_custom_type', None)


def test_redis_value_decode_string_plain() -> None:
    rv: models.Default = models.Default(key='plain_key')
    assert rv.decode_string(None) == ''
    assert rv.decode_string(b'test_value') == 'test_value'
    assert rv.decode_string('already_string') == 'already_string'


def test_redis_value_decode_string_base64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(redis_settings, 'BASE64_KEY_RE', re.compile(r'^b64:'))

    rv_valid: models.Default = models.Default(key='b64:secret')
    encoded: bytes = base64.b64encode(b'my_secret_payload')
    decoded: typing.Any = rv_valid.decode_string(encoded)
    assert decoded == 'my_secret_payload'
    assert rv_valid.base64 is True

    rv_invalid: models.Default = models.Default(key='b64:broken')
    decoded_broken: typing.Any = rv_invalid.decode_string(b'not_valid_b64!!!')
    assert decoded_broken == 'not_valid_b64!!!'
    assert rv_invalid.base64 is False


def test_redis_value_decode_string_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(redis_settings, 'JSON_KEY_RE', re.compile(r'^json:'))

    rv_valid: models.Default = models.Default(key='json:config')
    json_bytes: bytes = b'{"name": "test", "count": 42}'
    decoded: typing.Any = rv_valid.decode_string(json_bytes)
    assert decoded == {'name': 'test', 'count': 42}
    assert rv_valid.json is True

    rv_invalid: models.Default = models.Default(key='json:broken')
    decoded_broken: typing.Any = rv_invalid.decode_string(b'{bad json')
    assert decoded_broken == '{bad json'
    assert rv_invalid.json is False


def test_redis_value_custom_json_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CustomJsonModule:
        @staticmethod
        def loads(val: str) -> dict[str, str]:
            return {'parsed_by_custom': val}

    custom_re: re.Pattern[str] = re.compile(r'^custom_json:')
    monkeypatch.setattr(redis_settings, 'JSON_KEY_RE', custom_re)
    monkeypatch.setattr(redis_settings, 'JSON_MODULE', CustomJsonModule)

    rv: models.Default = models.Default(key='custom_json:item')
    decoded: typing.Any = rv.decode_string(b'raw_payload')
    assert decoded == {'parsed_by_custom': 'raw_payload'}
    assert rv.json is True


def test_redis_value_properties() -> None:
    rv: models.Default = models.Default(raw_value='test_raw')
    assert rv.value == 'test_raw'

    assert rv.ttl is None
    future_time: typing.Any = timezone.now() + timedelta(seconds=120)
    rv.expires_at = future_time
    assert rv.ttl is not None
    assert rv.ttl.total_seconds() > 0

    assert rv.idle is None
    past_time: typing.Any = timezone.now() - timedelta(seconds=60)
    rv.idle_since = past_time
    assert rv.idle is not None
    assert rv.idle.total_seconds() >= 0

    rv.raw_value = 'short_val'
    assert rv.cropped_value == 'short_val'
    assert rv.get_cropped_value(20) == 'short_val'

    long_str: str = 'x' * 100
    rv.raw_value = long_str
    cropped: str = rv.get_cropped_value(20)
    assert len(cropped) == 23
    assert cropped == ('x' * 10) + '...' + ('x' * 10)


def test_redis_value_getattr_repr_and_fetch_value() -> None:
    rv: models.Default = models.Default(key='repr_key', raw_value='short')
    assert repr(rv) == '<Default[repr_key] short>'

    with pytest.raises(
        AttributeError, match=r'Unknown attribute Default\.nonexistent_attr'
    ):
        _ = rv.nonexistent_attr

    mock_client: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    with pytest.raises(
        NotImplementedError, match="fetch_value is not implemented for ''"
    ):
        rv.fetch_value(mock_client)


def test_redis_string() -> None:
    mock_client: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_client.get.return_value = b'redis_value'

    rv: models.RedisString = models.RedisString(key='string_key')
    fetched: typing.Any = rv.fetch_value(mock_client)
    mock_client.get.assert_called_once_with('string_key')
    assert fetched == b'redis_value'

    object.__setattr__(rv, 'raw_value', b'string_data')
    assert rv.value == 'string_data'


def test_redis_list() -> None:
    mock_client: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_client.lrange.return_value = [b'item1', b'item2']

    rv: models.RedisList = models.RedisList(key='list_key')
    fetched: typing.Any = rv.fetch_value(mock_client)
    mock_client.lrange.assert_called_once_with('list_key', 0, -1)
    assert fetched == [b'item1', b'item2']

    object.__setattr__(rv, 'raw_value', [b'item1', b'item2'])
    assert rv.value == ['item1', 'item2']

    object.__setattr__(rv, 'raw_value', None)
    assert rv.value == []


def test_redis_set() -> None:
    mock_client: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_client.smembers.return_value = {b'member1', b'member2'}

    rv: models.RedisSet = models.RedisSet(key='set_key')
    fetched: typing.Any = rv.fetch_value(mock_client)
    mock_client.smembers.assert_called_once_with('set_key')
    assert fetched == {b'member1', b'member2'}

    object.__setattr__(rv, 'raw_value', {b'member1', b'member2'})
    assert rv.value == {'member1', 'member2'}

    object.__setattr__(rv, 'raw_value', None)
    assert rv.value == set()


def test_redis_hash() -> None:
    mock_client: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_client.hgetall.return_value = {b'field1': b'val1', b'field2': b'val2'}

    rv: models.RedisHash = models.RedisHash(key='hash_key')
    fetched: typing.Any = rv.fetch_value(mock_client)
    mock_client.hgetall.assert_called_once_with('hash_key')
    assert fetched == {b'field1': b'val1', b'field2': b'val2'}

    raw_hash: dict[bytes, bytes] = {b'field1': b'val1', b'field2': b'val2'}
    object.__setattr__(rv, 'raw_value', raw_hash)
    assert rv.value == {'field1': 'val1', 'field2': 'val2'}

    object.__setattr__(rv, 'raw_value', None)
    assert rv.value == {}


def test_redis_zset() -> None:
    mock_client: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_client.zrangebyscore.return_value = [(b'elem1', 1.0), (b'elem2', 2.5)]

    rv: models.RedisZSet = models.RedisZSet(key='zset_key')
    fetched: typing.Any = rv.fetch_value(mock_client)
    mock_client.zrangebyscore.assert_called_once_with(
        'zset_key', '-inf', '+inf', withscores=True
    )
    assert fetched == [(b'elem1', 1.0), (b'elem2', 2.5)]

    object.__setattr__(rv, 'raw_value', [(b'elem1', 1.0), (b'elem2', 2.5)])
    expected: collections.OrderedDict[str, typing.Any] = (
        collections.OrderedDict([('elem1', 1.0), ('elem2', 2.5)])
    )
    assert rv.value == expected

    object.__setattr__(rv, 'raw_value', None)
    assert rv.value == collections.OrderedDict()


@pytest.mark.filterwarnings('ignore::RuntimeWarning')
def test_server_models_dynamic_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_servers: dict[str, typing.Any] = {
        'dynamictest': {
            'meta': {'verbose_name': 'Dynamic Test'},
            'exclude_key_prefixes': ('dyn:',),
            'exclude_key_re': r'^dyn:',
            'exclude_keys': {'dyn_exact'},
        }
    }
    monkeypatch.setattr(redis_settings, 'SERVERS', custom_servers)

    importlib.reload(models)

    assert 'dynamictest' in models.server_models
    dyn_model: type[models.RedisValue] = models.server_models['dynamictest']
    meta_obj: typing.Any = dyn_model._meta
    assert meta_obj.verbose_name == 'Dynamic Test'
    assert meta_obj.exclude_key_prefixes == ('dyn:',)
    assert meta_obj.exclude_key_re == r'^dyn:'
    assert meta_obj.exclude_keys == {'dyn_exact'}

    monkeypatch.undo()
    importlib.reload(models)


def test_redis_value_str_is_the_key() -> None:
    value: models.RedisValue = models.RedisValue.create(
        key='menu:breakfast', type='list'
    )
    assert str(value) == 'menu:breakfast'


def test_app_config_verbose_name() -> None:
    from django.apps import apps

    assert apps.get_app_config('redis_admin').verbose_name == 'Redis'
