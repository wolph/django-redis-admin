"""Settings for the demo server.

Layers demo-only Redis settings over the test settings so the screenshots
and the quick start show every feature at once: two servers, JSON and base64
decoding selected by key pattern, and an excluded key prefix.

Point the demo at another Redis with the `REDIS_HOST` and `REDIS_PORT`
environment variables.
"""

from __future__ import annotations

import os
import typing

from .settings import *  # noqa: F403

REDIS_HOST: str = os.environ.get('REDIS_HOST', '127.0.0.1')
REDIS_PORT: int = int(os.environ.get('REDIS_PORT', '6379'))

# Every entry becomes its own model admin. The `default` server holds the
# application data, the `sessions` server is a second database on the same
# Redis to show how multiple servers appear in the admin.
REDIS_SERVERS: dict[str, dict[str, typing.Any]] = {
    'default': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 0,
        # Libraries such as django-constance store pickled values under this
        # prefix. Excluding them keeps the admin from trying to decode them.
        'exclude_key_prefixes': ('constance:',),
    },
    'sessions': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 1,
        'meta': {
            'verbose_name': 'session',
            'verbose_name_plural': 'sessions',
        },
    },
}

# Keys starting with `json:` are decoded as JSON, keys starting with
# `base64:` are decoded from base64 before they are shown.
REDIS_JSON_KEY_RE: str = r'^json:'
REDIS_BASE64_KEY_RE: str = r'^base64:'
