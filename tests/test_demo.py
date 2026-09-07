from __future__ import annotations

import importlib
import types
import typing

import pytest
import redis

from redis_admin import admin, models
from test_redis_admin import demo


def test_seed_default_writes_every_type(
    redis_client: redis.Redis[bytes],
) -> None:
    keys: list[str] = demo.seed_default(redis_client)

    present: set[str] = {k.decode() for k in redis_client.keys('*')}
    assert set(keys) <= present

    expected_types: dict[str, bytes] = {
        'greeting': b'string',
        'menu:breakfast': b'list',
        'tags': b'set',
        'user:1': b'hash',
        'leaderboard': b'zset',
        'json:settings': b'string',
        'base64:token': b'string',
    }
    # `Redis.type` is untyped in the stubs, so call it through an Any alias.
    raw: typing.Any = redis_client
    for key, type_ in expected_types.items():
        assert raw.type(key) == type_, key

    assert redis_client.ttl('session:spam') > 0
    assert len(demo.LONG_VALUE) > 150


def test_seed_default_is_repeatable(redis_client: redis.Redis[bytes]) -> None:
    demo.seed_default(redis_client)
    demo.seed_default(redis_client)

    assert redis_client.llen('menu:breakfast') == 5
    assert redis_client.scard('tags') == 3
    assert redis_client.zcard('leaderboard') == 3


def test_seed_sessions_sets_a_ttl(redis_client: redis.Redis[bytes]) -> None:
    keys: list[str] = demo.seed_sessions(redis_client)
    assert len(keys) == 3
    raw: typing.Any = redis_client
    for key in keys:
        assert raw.type(key) == b'hash'
        assert redis_client.ttl(key) > 0


def test_seeded_keys_show_up_in_the_admin(
    redis_client: redis.Redis[bytes],
) -> None:
    demo.seed_default(redis_client)
    qs: admin.Queryset = admin.Queryset(models.Default)
    listed: set[str] = {item.key for item in qs}
    assert 'greeting' in listed
    assert 'leaderboard' in listed


def test_seed_servers_only_seeds_known_servers(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    from redis_admin import settings as redis_settings

    servers: dict[str, typing.Any] = dict(redis_settings.SERVERS)
    servers['unknown'] = dict(servers['default'])
    monkeypatch.setattr(redis_settings, 'SERVERS', servers)

    seeded: dict[str, list[str]] = demo.seed_servers()
    assert set(seeded) == {'default'}
    assert redis_client.exists('greeting') == 1


@pytest.mark.django_db
def test_ensure_superuser_is_idempotent() -> None:
    first: typing.Any = demo.ensure_superuser()
    second: typing.Any = demo.ensure_superuser()

    assert first.pk == second.pk
    assert second.is_staff is True
    assert second.is_superuser is True
    assert second.check_password(demo.DEMO_PASSWORD)
    # The hash is left alone when the password already matches, so open
    # sessions survive a re-seed.
    assert first.password == second.password

    second.set_password('changed')
    second.save()
    third: typing.Any = demo.ensure_superuser()
    assert third.check_password(demo.DEMO_PASSWORD)


@pytest.mark.django_db
def test_main_seed_only(
    redis_client: redis.Redis[bytes], capsys: pytest.CaptureFixture[str]
) -> None:
    demo.main(['--seed-only'])

    out: str = capsys.readouterr().out
    assert "Seeded 11 keys on server 'default'" in out
    assert 'Login:' not in out
    assert redis_client.exists('greeting') == 1


def test_demo_settings_layer_over_test_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('REDIS_HOST', 'redis.example.com')
    monkeypatch.setenv('REDIS_PORT', '6390')

    module: types.ModuleType = importlib.reload(
        importlib.import_module('test_redis_admin.settings_demo')
    )

    servers: dict[str, dict[str, typing.Any]] = module.REDIS_SERVERS
    assert set(servers) == {'default', 'sessions'}
    assert servers['default']['host'] == 'redis.example.com'
    assert servers['sessions']['port'] == 6390
    assert servers['default']['exclude_key_prefixes'] == ('constance:',)
    assert module.INSTALLED_APPS[-1] == 'redis_admin'
