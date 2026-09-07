# The demo project

The repository ships a small Django project that seeds a Redis with sample
data and serves the admin. It produced every screenshot in these docs, and it
is the quickest way to see the admin before wiring it into your own project.

## Running it

You need a Redis on `127.0.0.1:6379` and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/wolph/django-redis-admin.git
cd django-redis-admin
uv sync
uv run python -m test_redis_admin.demo
```

The script migrates a SQLite database, creates a superuser, seeds Redis and
starts the development server:

```text
Seeded 11 keys on server 'default'
Seeded 3 keys on server 'sessions'
Admin: http://127.0.0.1:8080/admin/
Login: admin / admin
```

Log in with `admin` and `admin`. Pass `--port` to use another port and
`--seed-only` to seed without starting the server. The SQLite file lands next
to the settings and is ignored by git.

A Redis elsewhere works too:

```bash
REDIS_HOST=redis.internal REDIS_PORT=6380 uv run python -m test_redis_admin.demo
```

## What gets seeded

The `default` server, database `0`, receives one key of every type plus the
edge cases the admin handles:

| Key | Type | Shows |
| --- | --- | --- |
| `greeting` | string | A plain value |
| `counter:page_views` | string | An integer stored as a string |
| `session:spam` | string | An expiry and a TTL |
| `menu:breakfast` | list | Duplicates preserved |
| `tags` | set | An unordered set |
| `user:1` | hash | Field and value pairs |
| `leaderboard` | zset | Members with scores |
| `json:settings` | string | JSON decoding by key pattern |
| `base64:token` | string | Base64 decoding by key pattern |
| `report:2026` | string | Cropping of a long value |
| `constance:SITE_NAME` | string | A pickle, excluded by prefix |

The `sessions` server, database `1` on the same Redis, receives three hashes
with a time to live to show a second server with its own label.

Seeding never deletes keys, so it is safe to run against a Redis that already
holds data. Re-running it overwrites the sample keys and leaves the rest
alone.

## The demo settings

`test_redis_admin/settings_demo.py` layers the demo configuration over the
plain test settings. It is a compact example of the options from
{doc}`configuration`:

```python
REDIS_SERVERS = {
    'default': {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': 0,
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
REDIS_JSON_KEY_RE = r'^json:'
REDIS_BASE64_KEY_RE = r'^base64:'
```

The test suite uses the plain `test_redis_admin.settings` module and starts
its own Redis on a free port, so the demo and the tests never share state.
