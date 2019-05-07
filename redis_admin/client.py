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


def get_master(name) -> redis.Redis:
    server = settings.SERVERS.get(name, {}).copy()
    if 'service_name' in server:
        server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Getting master from sentinel %s: %r', name, server)
        server.pop('meta', dict())
        return get_sentinel().master_for(**server)
    else:
        if name not in masters:
            if 'master' in server:
                server = server['master']

            server.pop('meta', dict())
            server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
            logger.debug('Connecting to master %s: %r', name, server)
            masters[name] = redis.Redis(**server)

        return masters[name]


def get_slave(name) -> redis.Redis:
    server = settings.SERVERS.get(name, {})
    if 'service_name' in server:
        server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
        logger.debug('Getting slave from sentinel %s: %r', name, server)
        server.pop('meta', dict())
        return get_sentinel().slave_for(**server)
    else:
        if name not in slaves:
            if 'slave' in server:
                server = server['slave']

            server.pop('meta', dict())
            server.setdefault('socket_timeout', settings.SOCKET_TIMEOUT)
            logger.debug('Connecting to slave %s: %r', name, server)
            slaves[name] = redis.Redis(**server)

        return slaves[name]

