import logging
import typing

import redis
from redis import sentinel

from . import settings

logger: logging.Logger = logging.getLogger(__name__)
_sentinel: sentinel.Sentinel | None = None
masters: dict[str, redis.Redis] = {}
slaves: dict[str, redis.Redis] = {}


def get_sentinel() -> sentinel.Sentinel:
    global _sentinel
    if not _sentinel:
        options: dict[str, typing.Any] = settings.SENTINEL_OPTIONS
        options.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        _sentinel = sentinel.Sentinel(settings.SENTINELS, **options)

    return _sentinel


def _clean_server_options(
    server: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    cleaned: dict[str, typing.Any] = server.copy()
    cleaned.pop('meta', None)
    cleaned.pop('exclude_key_prefixes', None)
    cleaned.pop('exclude_key_re', None)
    cleaned.pop('exclude_keys', None)
    return cleaned


def get_master(name: str) -> redis.Redis:
    server: dict[str, typing.Any] = settings.SERVERS.get(name, {}).copy()
    if 'service_name' in server:
        server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Getting master from sentinel %s: %r', name, server)
        cleaned_server: dict[str, typing.Any] = _clean_server_options(server)
        return get_sentinel().master_for(**cleaned_server)

    if name not in masters:
        master_server: dict[str, typing.Any] = (
            server['master'].copy() if 'master' in server else server
        )
        cleaned_master: dict[str, typing.Any] = _clean_server_options(
            master_server
        )
        cleaned_master.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Connecting to master %s: %r', name, cleaned_master)
        masters[name] = redis.Redis(**cleaned_master)

    return masters[name]


def get_slave(name: str) -> redis.Redis:
    server: dict[str, typing.Any] = settings.SERVERS.get(name, {}).copy()
    if 'service_name' in server:
        server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Getting slave from sentinel %s: %r', name, server)
        cleaned_server: dict[str, typing.Any] = _clean_server_options(server)
        return get_sentinel().slave_for(**cleaned_server)

    if name not in slaves:
        slave_server: dict[str, typing.Any] = (
            server['slave'].copy() if 'slave' in server else server
        )
        cleaned_slave: dict[str, typing.Any] = _clean_server_options(
            slave_server
        )
        cleaned_slave.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Connecting to slave %s: %r', name, cleaned_slave)
        slaves[name] = redis.Redis(**cleaned_slave)

    return slaves[name]
