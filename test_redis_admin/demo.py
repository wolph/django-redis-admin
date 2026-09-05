#!/usr/bin/env python
"""Seed Redis with sample data and run the demo admin.

Usage:

    uv run python -m test_redis_admin.demo [--port 8080] [--seed-only]

The script migrates the SQLite database, creates the `admin`/`admin`
superuser, seeds every configured Redis server with sample keys and starts
the development server. It needs a running Redis, by default on
`127.0.0.1:6379`. Re-running it overwrites the sample keys and leaves every
other key alone.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pickle
import typing

if typing.TYPE_CHECKING:
    import redis
    from django.contrib.auth.models import User

DEMO_USERNAME: str = 'admin'
DEMO_PASSWORD: str = 'admin'
DEMO_SETTINGS_MODULE: str = 'test_redis_admin.settings_demo'
DEFAULT_PORT: int = 8080

# A value comfortably over REDIS_REPR_CROP_SIZE so the list view crops it.
LONG_VALUE: str = ' '.join(
    f'line {n}: the quick brown fox jumps over the lazy dog'
    for n in range(1, 11)
)


def seed_default(client: redis.Redis[bytes]) -> list[str]:
    """Write one key of every supported type and return the key names."""
    pipe: redis.client.Pipeline[bytes] = client.pipeline()
    pipe.set('greeting', 'Hello from django-redis-admin')
    pipe.set('counter:page_views', 4242)
    pipe.set('session:spam', 'eggs', ex=3600)
    # RPUSH appends, so reset the list or every run would grow the menu.
    pipe.delete('menu:breakfast')
    pipe.rpush('menu:breakfast', 'spam', 'eggs', 'spam', 'bacon', 'spam')
    pipe.sadd('tags', 'python', 'django', 'redis')
    pipe.hset(
        'user:1',
        mapping={
            'name': 'Brian',
            'email': 'brian@example.com',
            'role': 'staff',
        },
    )
    pipe.zadd('leaderboard', {'alice': 1200, 'bob': 950, 'carol': 1420})
    pipe.set(
        'json:settings',
        json.dumps({'debug': True, 'retries': 3, 'hosts': ['a', 'b']}),
    )
    pipe.set(
        'base64:token',
        base64.b64encode(b'a base64 encoded value').decode(),
    )
    pipe.set('report:2026', LONG_VALUE)
    # Pickled data as django-constance stores it. The demo settings exclude
    # this prefix, so the key exists in Redis but stays out of the admin.
    pipe.set('constance:SITE_NAME', pickle.dumps('Spam Inc.'))
    pipe.execute()
    return [
        'greeting',
        'counter:page_views',
        'session:spam',
        'menu:breakfast',
        'tags',
        'user:1',
        'leaderboard',
        'json:settings',
        'base64:token',
        'report:2026',
        'constance:SITE_NAME',
    ]


def seed_sessions(client: redis.Redis[bytes]) -> list[str]:
    """Write a few session-like hashes with a time to live."""
    pipe: redis.client.Pipeline[bytes] = client.pipeline()
    keys: list[str] = []
    for n, user in enumerate(('alice', 'bob', 'carol'), start=1):
        key: str = f'session:{n:04d}'
        pipe.hset(key, mapping={'user': user, 'ip': f'10.0.0.{n}'})
        pipe.expire(key, 1800 * n)
        keys.append(key)
    pipe.execute()
    return keys


SEEDERS: dict[str, typing.Callable[[redis.Redis[bytes]], list[str]]] = {
    'default': seed_default,
    'sessions': seed_sessions,
}


def ensure_superuser(
    username: str = DEMO_USERNAME, password: str = DEMO_PASSWORD
) -> User:
    """Create or update the demo superuser and return it."""
    from django.contrib.auth.models import User

    # Without the mypy plugin the manager's generic parameter is unknown to
    # pyright, so route the lookup through an Any-typed alias.
    user_model: typing.Any = User
    user: User = user_model.objects.get_or_create(username=username)[0]
    user.is_staff = True
    user.is_superuser = True
    # Resetting an unchanged password would still rotate the session hash
    # and log every browser out on each re-seed.
    if not user.check_password(password):
        user.set_password(password)
    user.save()
    return user


def seed_servers() -> dict[str, list[str]]:
    """Seed every configured server that has a seeder and report the keys."""
    from redis_admin import (
        client,
        settings as redis_settings,
    )

    seeded: dict[str, list[str]] = {}
    for name in redis_settings.SERVERS:
        seeder: typing.Callable[[redis.Redis[bytes]], list[str]] | None = (
            SEEDERS.get(name)
        )
        if seeder is not None:
            seeded[name] = seeder(client.get_master(name))
    return seeded


def parse_args(argv: typing.Sequence[str] | None = None) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_PORT,
        help=f'port for the development server (default: {DEFAULT_PORT})',
    )
    parser.add_argument(
        '--seed-only',
        action='store_true',
        help='migrate, create the superuser and seed Redis, then exit',
    )
    return parser.parse_args(argv)


def main(argv: typing.Sequence[str] | None = None) -> None:
    args: argparse.Namespace = parse_args(argv)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEMO_SETTINGS_MODULE)

    import django

    django.setup()

    from django.core.management import call_command

    call_command('migrate', verbosity=0)
    ensure_superuser()
    for name, keys in seed_servers().items():
        print(f'Seeded {len(keys)} keys on server {name!r}')

    if args.seed_only:
        return

    print(f'Admin: http://127.0.0.1:{args.port}/admin/')
    print(f'Login: {DEMO_USERNAME} / {DEMO_PASSWORD}')
    # The autoreloader would re-run this module, and with it the seeding,
    # on every code change.
    call_command('runserver', f'127.0.0.1:{args.port}', use_reloader=False)


if __name__ == '__main__':
    main()
