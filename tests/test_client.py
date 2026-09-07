# pyright: reportPrivateUsage=false
from __future__ import annotations

import typing
from unittest import mock

import pytest
import redis
from redis import sentinel

from redis_admin import (
    client,
    settings as redis_settings,
)
from tests.conftest import MockSentinel


def test_clean_server_options() -> None:
    server_dict: dict[str, typing.Any] = {
        'host': '127.0.0.1',
        'port': 6379,
        'meta': {'app_label': 'redis_admin'},
        'exclude_key_prefixes': ('prefix:',),
        'exclude_key_re': r'^pattern:',
        'exclude_keys': {'secret'},
        'extra_option': True,
    }
    cleaned: dict[str, typing.Any] = client._clean_server_options(server_dict)
    assert cleaned == {
        'host': '127.0.0.1',
        'port': 6379,
        'extra_option': True,
    }


def test_get_sentinel_default_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client, '_sentinel', None)
    monkeypatch.setattr(redis_settings, 'SENTINELS', [('127.0.0.1', 26379)])
    monkeypatch.setattr(redis_settings, 'SENTINEL_OPTIONS', {})
    monkeypatch.setattr(redis_settings, 'SOCKET_TIMEOUT', 0.5)

    created_sentinels: list[typing.Any] = []

    def mock_sentinel_init(
        sentinels: list[typing.Any], **kwargs: typing.Any
    ) -> sentinel.Sentinel:
        created_sentinels.append((sentinels, kwargs))
        mock_obj: sentinel.Sentinel = mock.MagicMock(spec=sentinel.Sentinel)
        return mock_obj

    monkeypatch.setattr(sentinel, 'Sentinel', mock_sentinel_init)

    s1: sentinel.Sentinel = client.get_sentinel()
    assert len(created_sentinels) == 1
    assert created_sentinels[0][0] == [('127.0.0.1', 26379)]
    assert created_sentinels[0][1]['socket_timeout'] == 0.5

    s2: sentinel.Sentinel = client.get_sentinel()
    assert s1 is s2
    assert len(created_sentinels) == 1


def test_get_sentinel_custom_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client, '_sentinel', None)
    monkeypatch.setattr(redis_settings, 'SENTINELS', [('localhost', 26379)])
    monkeypatch.setattr(
        redis_settings,
        'SENTINEL_OPTIONS',
        {'socket_timeout': 1.5, 'password': 'secret'},
    )

    created_sentinels: list[typing.Any] = []

    def mock_sentinel_init(
        sentinels: list[typing.Any], **kwargs: typing.Any
    ) -> sentinel.Sentinel:
        created_sentinels.append((sentinels, kwargs))
        mock_obj: sentinel.Sentinel = mock.MagicMock(spec=sentinel.Sentinel)
        return mock_obj

    monkeypatch.setattr(sentinel, 'Sentinel', mock_sentinel_init)

    s: sentinel.Sentinel = client.get_sentinel()
    assert s is not None
    assert len(created_sentinels) == 1
    assert created_sentinels[0][1]['socket_timeout'] == 1.5
    assert created_sentinels[0][1]['password'] == 'secret'


def test_get_master_sentinel(
    monkeypatch: pytest.MonkeyPatch, mock_sentinel: MockSentinel
) -> None:
    mock_redis: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_sentinel.master_dict['mymaster'] = mock_redis

    server_config: dict[str, typing.Any] = {
        'service_name': 'mymaster',
        'meta': {'app_label': 'redis_admin'},
        'exclude_keys': {'secret'},
    }
    monkeypatch.setattr(
        redis_settings, 'SERVERS', {'sentinel_server': server_config}
    )

    master: redis.Redis[bytes] = client.get_master('sentinel_server')
    assert master is mock_redis


def test_get_slave_sentinel(
    monkeypatch: pytest.MonkeyPatch, mock_sentinel: MockSentinel
) -> None:
    mock_redis: mock.MagicMock = mock.MagicMock(spec=redis.Redis)
    mock_sentinel.slave_dict['mymaster'] = mock_redis

    server_config: dict[str, typing.Any] = {
        'service_name': 'mymaster',
        'meta': {'app_label': 'redis_admin'},
        'exclude_keys': {'secret'},
    }
    monkeypatch.setattr(
        redis_settings, 'SERVERS', {'sentinel_server': server_config}
    )

    slave: redis.Redis[bytes] = client.get_slave('sentinel_server')
    assert slave is mock_redis


def test_get_master_direct_and_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.masters.clear()
    created_clients: list[dict[str, typing.Any]] = []

    def mock_redis_init(**kwargs: typing.Any) -> redis.Redis[bytes]:
        created_clients.append(kwargs)
        return mock.MagicMock(spec=redis.Redis)

    monkeypatch.setattr(redis, 'Redis', mock_redis_init)

    server_config: dict[str, typing.Any] = {
        'host': '127.0.0.1',
        'port': 6379,
        'meta': {'app_label': 'redis_admin'},
    }
    monkeypatch.setattr(
        redis_settings, 'SERVERS', {'direct_server': server_config}
    )

    m1: redis.Redis[bytes] = client.get_master('direct_server')
    assert len(created_clients) == 1
    assert created_clients[0]['host'] == '127.0.0.1'
    assert created_clients[0]['port'] == 6379
    assert 'meta' not in created_clients[0]
    expected_timeout: float = redis_settings.SOCKET_TIMEOUT
    assert created_clients[0]['socket_timeout'] == expected_timeout

    m2: redis.Redis[bytes] = client.get_master('direct_server')
    assert m1 is m2
    assert len(created_clients) == 1


def test_get_slave_direct_and_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.slaves.clear()
    created_clients: list[dict[str, typing.Any]] = []

    def mock_redis_init(**kwargs: typing.Any) -> redis.Redis[bytes]:
        created_clients.append(kwargs)
        return mock.MagicMock(spec=redis.Redis)

    monkeypatch.setattr(redis, 'Redis', mock_redis_init)

    server_config: dict[str, typing.Any] = {
        'host': '127.0.0.1',
        'port': 6380,
        'exclude_keys': {'foo'},
    }
    monkeypatch.setattr(
        redis_settings, 'SERVERS', {'direct_slave': server_config}
    )

    s1: redis.Redis[bytes] = client.get_slave('direct_slave')
    assert len(created_clients) == 1
    assert created_clients[0]['host'] == '127.0.0.1'
    assert created_clients[0]['port'] == 6380
    assert 'exclude_keys' not in created_clients[0]

    s2: redis.Redis[bytes] = client.get_slave('direct_slave')
    assert s1 is s2
    assert len(created_clients) == 1


def test_get_master_with_subdictionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.masters.clear()
    created_clients: list[dict[str, typing.Any]] = []

    def mock_redis_init(**kwargs: typing.Any) -> redis.Redis[bytes]:
        created_clients.append(kwargs)
        return mock.MagicMock(spec=redis.Redis)

    monkeypatch.setattr(redis, 'Redis', mock_redis_init)

    server_config: dict[str, typing.Any] = {
        'master': {
            'host': '127.0.0.1',
            'port': 6379,
            'meta': {'app_label': 'redis_admin'},
        },
        'slave': {'host': '127.0.0.1', 'port': 6380},
    }
    monkeypatch.setattr(
        redis_settings, 'SERVERS', {'split_server': server_config}
    )

    m: redis.Redis[bytes] = client.get_master('split_server')
    assert m is not None
    assert len(created_clients) == 1
    assert created_clients[0]['host'] == '127.0.0.1'
    assert created_clients[0]['port'] == 6379
    assert 'meta' not in created_clients[0]


def test_get_slave_with_subdictionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.slaves.clear()
    created_clients: list[dict[str, typing.Any]] = []

    def mock_redis_init(**kwargs: typing.Any) -> redis.Redis[bytes]:
        created_clients.append(kwargs)
        return mock.MagicMock(spec=redis.Redis)

    monkeypatch.setattr(redis, 'Redis', mock_redis_init)

    server_config: dict[str, typing.Any] = {
        'master': {'host': '127.0.0.1', 'port': 6379},
        'slave': {
            'host': '127.0.0.1',
            'port': 6380,
            'exclude_key_prefixes': ('prefix:',),
        },
    }
    monkeypatch.setattr(
        redis_settings, 'SERVERS', {'split_server': server_config}
    )

    s: redis.Redis[bytes] = client.get_slave('split_server')
    assert s is not None
    assert len(created_clients) == 1
    assert created_clients[0]['host'] == '127.0.0.1'
    assert created_clients[0]['port'] == 6380
    assert 'exclude_key_prefixes' not in created_clients[0]


def test_get_master_and_slave_unknown_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.masters.clear()
    client.slaves.clear()
    created_clients: list[dict[str, typing.Any]] = []

    def mock_redis_init(**kwargs: typing.Any) -> redis.Redis[bytes]:
        created_clients.append(kwargs)
        return mock.MagicMock(spec=redis.Redis)

    monkeypatch.setattr(redis, 'Redis', mock_redis_init)
    monkeypatch.setattr(redis_settings, 'SERVERS', {})

    m: redis.Redis[bytes] = client.get_master('non_existent')
    s: redis.Redis[bytes] = client.get_slave('non_existent')
    assert m is not None
    assert s is not None
    assert len(created_clients) == 2
