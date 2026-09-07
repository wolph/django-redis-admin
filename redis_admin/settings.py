from __future__ import annotations

import re
import typing

from django.conf import settings

#: Default socket timeout if no other settings are given.
SOCKET_TIMEOUT: float = getattr(settings, 'REDIS_SOCKET_TIMEOUT', 0.3)

#: The `REDIS_SENTINELS` setting should be a list containing host/port
#: combinations. As documented here:
#: https://github.com/andymccurdy/redis-py/blob/master/README.rst#sentinel-support
#: For example:
#: [('server_a', 26379), ('server_b', 26379)]
SENTINELS: list[typing.Any] = getattr(settings, 'REDIS_SENTINELS', [])
assert isinstance(SENTINELS, list)

#: The `REDIS_SENTINEL_OPTIONS` are the extra arguments to
#: `redis.sentinel.Sentinel`:
#: https://github.com/andymccurdy/redis-py/blob/cdfe2befbe00db4a3c48c9ddd6d64dea15f6f0db/redis/sentinel.py#L128-L155
SENTINEL_OPTIONS: dict[str, typing.Any] = getattr(
    settings, 'REDIS_SENTINEL_OPTIONS', {}
)
SENTINEL_OPTIONS.setdefault('socket_timeout', SOCKET_TIMEOUT)

#: The `REDIS_SERVERS` setting configures the servers to be queried. Every
#: server will get it's own model admin. To connect through `Sentinel` a
#: `service_name` parameter must be specified.
#: If no `service_name` is available we will connect to the server(s) directly.
#
#: To use a separate `master`/`slave` configuration `master`/`slave`
#: sub-dictionaries can be provided. Otherwise the top-level dictionary will be
#: passed along to `redis.Redis`:
#: https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
SERVERS: dict[str, typing.Any] = getattr(
    settings, 'REDIS_SERVERS', {'default': {}}
)

#: The maximum amount of characters to show before cropping them in the admin
#: list view
CROP_SIZE: int = getattr(settings, 'REDIS_REPR_CROP_SIZE', 150)

JSON_KEY_RE: re.Pattern[str] = re.compile(
    getattr(settings, 'REDIS_JSON_KEY_RE', '^$')
)
BASE64_KEY_RE: re.Pattern[str] = re.compile(
    getattr(settings, 'REDIS_BASE64_KEY_RE', '^$')
)

#: Can be any importable module that has a `loads` and `dumps` function
JSON_MODULE: typing.Any = __import__(
    getattr(settings, 'REDIS_JSON_MODULE', 'json')
)


def _get_exclude_key_prefixes(raw: typing.Any) -> tuple[str, ...]:
    if not raw:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(raw)


def _get_exclude_key_re(raw: typing.Any) -> re.Pattern[str] | None:
    if not raw:
        return None
    if isinstance(raw, str):
        return re.compile(raw)
    if isinstance(raw, re.Pattern):
        return typing.cast(re.Pattern[str], raw)
    return None


def _get_exclude_keys(raw: typing.Any) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, str):
        return {raw}
    return set(raw)


#: Key prefixes that should be excluded from the admin interface
EXCLUDE_KEY_PREFIXES: tuple[str, ...] = _get_exclude_key_prefixes(
    getattr(settings, 'REDIS_EXCLUDE_KEY_PREFIXES', ())
)

#: Regex pattern for keys that should be excluded from the admin interface
EXCLUDE_KEY_RE: re.Pattern[str] | None = _get_exclude_key_re(
    getattr(settings, 'REDIS_EXCLUDE_KEY_RE', None)
)

#: Exact keys that should be excluded from the admin interface
EXCLUDE_KEYS: set[str] = _get_exclude_keys(
    getattr(settings, 'REDIS_EXCLUDE_KEYS', ())
)

get_exclude_key_prefixes = _get_exclude_key_prefixes
get_exclude_key_re = _get_exclude_key_re
get_exclude_keys = _get_exclude_keys
