import redis
import logging
from redis import sentinel

from . import settings


logger = logging.getLogger(__name__)
_sentinel = None
masters = dict()
slaves = dict()


def get_sentinel():
    global _sentinel
    if not _sentinel:
        options = settings.SENTINEL_OPTIONS
        options.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        _sentinel = sentinel.Sentinel(settings.SENTINELS, **options)

    return _sentinel


def _clean_server_options(server: dict) -> dict:
    cleaned: dict = server.copy()
    cleaned.pop('meta', None)
    cleaned.pop('exclude_key_prefixes', None)
    cleaned.pop('exclude_key_re', None)
    cleaned.pop('exclude_keys', None)
    return cleaned


def get_master(name: str) -> redis.Redis:
    server: dict = settings.SERVERS.get(name, {}).copy()
    if 'service_name' in server:
        server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Getting master from sentinel %s: %r', name, server)
        cleaned_server: dict = _clean_server_options(server)
        return get_sentinel().master_for(**cleaned_server)
    else:
        if name not in masters:
            master_server: dict = server['master'].copy() if 'master' in server else server
            cleaned_master: dict = _clean_server_options(master_server)
            cleaned_master.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
            logger.debug('Connecting to master %s: %r', name, cleaned_master)
            masters[name] = redis.Redis(**cleaned_master)

        return masters[name]


def get_slave(name: str) -> redis.Redis:
    server: dict = settings.SERVERS.get(name, {}).copy()
    if 'service_name' in server:
        server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Getting slave from sentinel %s: %r', name, server)
        cleaned_server: dict = _clean_server_options(server)
        return get_sentinel().slave_for(**cleaned_server)
    else:
        if name not in slaves:
            slave_server: dict = server['slave'].copy() if 'slave' in server else server
            cleaned_slave: dict = _clean_server_options(slave_server)
            cleaned_slave.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
            logger.debug('Connecting to slave %s: %r', name, cleaned_slave)
            slaves[name] = redis.Redis(**cleaned_slave)

        return slaves[name]

