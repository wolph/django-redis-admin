from __future__ import annotations

import os
import socket
import subprocess
import time
import typing

import django
import pytest
import redis

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_redis_admin.settings')
django.setup()

from django.conf import settings as django_settings  # noqa: E402

from redis_admin import (  # noqa: E402
    client,
    settings as redis_settings,
)


def get_free_port() -> int:
    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port: int = int(sock.getsockname()[1])
    sock.close()
    return port


@pytest.fixture(scope='session')
def redis_server_port() -> typing.Generator[int, None, None]:
    port: int = get_free_port()
    proc: subprocess.Popen[bytes] = subprocess.Popen(
        [
            'redis-server',
            '--port',
            str(port),
            '--save',
            '',
            '--appendonly',
            'no',
            '--daemonize',
            'no',
            '--dir',
            '/tmp',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    test_client: redis.Redis[bytes] = redis.Redis(host='127.0.0.1', port=port)
    connected: bool = False
    for _ in range(50):
        try:
            if test_client.ping():
                connected = True
                break
        except Exception:
            time.sleep(0.05)

    if not connected:
        proc.terminate()
        proc.wait()
        raise RuntimeError(
            f'Could not connect to test redis-server on port {port}'
        )

    yield port

    proc.terminate()
    proc.wait()


@pytest.fixture
def redis_client(
    redis_server_port: int,
) -> typing.Generator[redis.Redis[bytes], None, None]:
    server_conf: dict[str, typing.Any] = {
        'host': '127.0.0.1',
        'port': redis_server_port,
    }
    django_settings.REDIS_SERVERS = {'default': server_conf}
    redis_settings.SERVERS = {'default': server_conf}
    client.masters.clear()
    client.slaves.clear()

    r: redis.Redis[bytes] = redis.Redis(
        host='127.0.0.1', port=redis_server_port
    )
    r.flushdb()

    yield r

    r.flushdb()
    client.masters.clear()
    client.slaves.clear()


class MockSentinel:
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.args: tuple[typing.Any, ...] = args
        self.kwargs: dict[str, typing.Any] = kwargs
        self.master_dict: dict[str, typing.Any] = {}
        self.slave_dict: dict[str, typing.Any] = {}

    def master_for(
        self, service_name: str, **kwargs: typing.Any
    ) -> typing.Any:
        return self.master_dict.get(service_name, f'master_{service_name}')

    def slave_for(self, service_name: str, **kwargs: typing.Any) -> typing.Any:
        return self.slave_dict.get(service_name, f'slave_{service_name}')


@pytest.fixture
def mock_sentinel(monkeypatch: pytest.MonkeyPatch) -> MockSentinel:
    sentinel_instance: MockSentinel = MockSentinel()
    monkeypatch.setattr(client, '_sentinel', sentinel_instance)
    return sentinel_instance
