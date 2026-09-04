# pyright: reportPrivateUsage=false
from __future__ import annotations

import re
import typing

import pytest
import redis
from django.conf import settings as django_settings

from redis_admin import (
    admin,
    models,
    settings as redis_settings,
)


def test_exclude_key_prefixes_global(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('constance:BAR', 'val2')
    redis_client.set('myapp:USER', 'val3')

    monkeypatch.setattr(
        redis_settings, 'EXCLUDE_KEY_PREFIXES', ('constance:',), raising=False
    )
    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('constance:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert 'myapp:USER' in keys
    assert 'constance:FOO' not in keys
    assert 'constance:BAR' not in keys


def test_exclude_key_prefixes_per_server(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('myapp:USER', 'val2')

    monkeypatch.setattr(
        models.Default._meta,
        'exclude_key_prefixes',
        ('constance:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['myapp:USER']


def test_exclude_key_re_global(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('cache:SESSION', 'val2')
    redis_client.set('myapp:USER', 'val3')

    monkeypatch.setattr(
        redis_settings, 'EXCLUDE_KEY_RE', r'^(constance|cache):', raising=False
    )
    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_RE',
        r'^(constance|cache):',
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['myapp:USER']


def test_exclude_keys_exact(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('secret_key', 'val1')
    redis_client.set('normal_key', 'val2')

    monkeypatch.setattr(
        redis_settings, 'EXCLUDE_KEYS', ('secret_key',), raising=False
    )
    monkeypatch.setattr(
        django_settings, 'REDIS_EXCLUDE_KEYS', ('secret_key',), raising=False
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['normal_key']


def test_exclude_get_raises_does_not_exist(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('myapp:USER', 'val2')

    monkeypatch.setattr(
        redis_settings, 'EXCLUDE_KEY_PREFIXES', ('constance:',), raising=False
    )
    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('constance:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    found_item: models.RedisValue = qs.get(key='myapp:USER')
    assert found_item.key == 'myapp:USER'

    with pytest.raises(models.Default.DoesNotExist):
        qs.get(key='constance:FOO')


def test_exclude_filter_search(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('myapp:USER', 'val2')

    monkeypatch.setattr(
        redis_settings, 'EXCLUDE_KEY_PREFIXES', ('constance:',), raising=False
    )
    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('constance:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    filtered_keys: list[str] = [
        item.key for item in qs.filter(key__contains='constance')
    ]
    assert filtered_keys == []


def test_exclude_pagination(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    for i in range(30):
        redis_client.set(f'constance:key_{i:02d}', f'c_val_{i}')
        redis_client.set(f'myapp:key_{i:02d}', f'm_val_{i}')

    monkeypatch.setattr(
        redis_settings, 'EXCLUDE_KEY_PREFIXES', ('constance:',), raising=False
    )
    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('constance:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    paged_items: list[models.RedisValue] = list(qs[:20])

    assert len(paged_items) == 20
    for item in paged_items:
        assert item.key.startswith('myapp:')


def test_no_exclusions_by_default(redis_client: redis.Redis[bytes]) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('myapp:USER', 'val2')

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: set[str] = {item.key for item in qs}

    assert keys == {'constance:FOO', 'myapp:USER'}


def test_exclude_single_string_prefix_and_key(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('single_exact_key', 'val2')
    redis_client.set('kept_key', 'val3')

    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        'constance:',
        raising=False,
    )
    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEYS',
        'single_exact_key',
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['kept_key']


def test_exclude_compiled_regex(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('constance:FOO', 'val1')
    redis_client.set('normal_key', 'val2')

    pattern: re.Pattern[str] = re.compile(r'^constance:')
    monkeypatch.setattr(
        django_settings, 'REDIS_EXCLUDE_KEY_RE', pattern, raising=False
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['normal_key']


def test_exclude_various_redis_types(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.rpush('constance:list', 'item1', 'item2')
    redis_client.sadd('constance:set', 's1', 's2')
    redis_client.hset('constance:hash', 'k1', 'v1')
    redis_client.zadd('constance:zset', {'z1': 1.0})
    redis_client.set('myapp:string', 'val')

    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('constance:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['myapp:string']


def test_exclude_combines_meta_and_global(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('global_prefix:1', 'val1')
    redis_client.set('meta_prefix:2', 'val2')
    redis_client.set('keep_me', 'val3')

    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('global_prefix:',),
        raising=False,
    )
    monkeypatch.setattr(
        models.Default._meta,
        'exclude_key_prefixes',
        ('meta_prefix:',),
        raising=False,
    )

    qs: admin.Queryset = admin.Queryset(models.Default)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['keep_me']


def test_redis_admin_get_queryset(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory

    redis_client.set('constance:FOO', 'val1')
    redis_client.set('myapp:BAR', 'val2')

    monkeypatch.setattr(
        django_settings,
        'REDIS_EXCLUDE_KEY_PREFIXES',
        ('constance:',),
        raising=False,
    )

    factory: RequestFactory = RequestFactory()
    request: typing.Any = factory.get('/admin/redis_admin/default/')

    site: AdminSite = AdminSite()
    model_admin: admin.RedisAdmin = admin.RedisAdmin(models.Default, site)
    qs: admin.Queryset = model_admin.get_queryset(request)
    keys: list[str] = [item.key for item in qs]

    assert keys == ['myapp:BAR']
