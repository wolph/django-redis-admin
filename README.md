<div align="center">

# Django Redis Admin

**Browse every key on your Redis servers from the Django admin you already have.**

[![PyPI version](https://img.shields.io/pypi/v/django-redis-admin.svg?logo=pypi&logoColor=white)](https://pypi.org/project/django-redis-admin/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-redis-admin.svg?logo=python&logoColor=white)](https://pypi.org/project/django-redis-admin/)
[![Django versions](https://img.shields.io/pypi/djversions/django-redis-admin.svg?logo=django&logoColor=white)](https://pypi.org/project/django-redis-admin/)
[![CI](https://github.com/wolph/django-redis-admin/actions/workflows/ci.yml/badge.svg)](https://github.com/wolph/django-redis-admin/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/readthedocs/django-redis-admin.svg?logo=readthedocs&logoColor=white)](https://django-redis-admin.readthedocs.io/)
[![Typed](https://img.shields.io/badge/typed-mypy%20%7C%20pyright%20%7C%20pyrefly-blue.svg)](https://github.com/wolph/django-redis-admin)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/pypi/l/django-redis-admin.svg)](https://github.com/wolph/django-redis-admin/blob/develop/LICENSE)

[**Documentation**](https://django-redis-admin.readthedocs.io/) ·
[**PyPI**](https://pypi.org/project/django-redis-admin/) ·
[**Source**](https://github.com/wolph/django-redis-admin) ·
[**Issues**](https://github.com/wolph/django-redis-admin/issues)

</div>

![The Redis key list in the Django admin: key, type, expiry, TTL, idle time, a cropped value and JSON and base64 flags](https://raw.githubusercontent.com/wolph/django-redis-admin/develop/docs/_static/changelist.png)

You have a Redis server next to your Django project and a question about it:
which keys are in there, what do they hold, and when do they expire? Answering
that from `redis-cli` means remembering `SCAN`, `TYPE`, `PTTL` and a decoder
for whatever your code stored. `django-redis-admin` puts the same answers in
the Django admin as a searchable, paginated list with one page per key.

The trick underneath is small. A fake queryset talks to Redis with `SCAN` and a
pipeline of `TYPE`, `PTTL` and `OBJECT IDLETIME`, and the `ModelAdmin` never
notices it isn't looking at a database table. Because Redis only stores bytes,
the admin can decode JSON and base64 values for you, selected by a regular
expression on the key.

## Highlights

- **Every server, every key type.** Strings, lists, sets, hashes and sorted
  sets from plain servers, master and replica pairs, or Redis Sentinel.
- **Search and pagination that map onto `SCAN`.** `exact`, `startswith`,
  `endswith` and `contains` lookups on the key become glob patterns.
- **Decoding by key pattern.** JSON and base64 values are decoded before they
  are shown, and the list flags which keys matched.
- **Exclusions for keys that aren't yours.** Hide pickled `constance:` values
  or session stores by prefix, regular expression or exact key.
- **Read-only by design.** Add, change and delete are refused at the endpoint,
  so a staff account with the view permission can look but never touch.
- **Typed and tested.** Ships `py.typed`, passes mypy, basedpyright and pyrefly
  in strict mode, and runs at 100% line and branch coverage on Python 3.10 to
  3.14 and PyPy with Django 4.2 to 6.1.

## Quick start

Install the package:

```bash
pip install django-redis-admin
```

Add it to `INSTALLED_APPS` in your Django settings:

```python
INSTALLED_APPS = [
    ...,
    'django.contrib.admin',
    'redis_admin',
]
```

That's the whole setup for a Redis on `localhost:6379`. Start your server, log
in to `/admin/` and a **Redis** section appears with one entry per configured
server. For other hosts, ports or databases add a `REDIS_SERVERS` setting:

```python
REDIS_SERVERS = {
    'cache': {'host': 'redis.internal', 'port': 6379, 'db': 1},
    'sessions': {'host': 'redis.internal', 'port': 6379, 'db': 2},
}
```

Each entry becomes its own admin page, named after the key. The
[configuration reference](https://django-redis-admin.readthedocs.io/en/latest/configuration.html)
covers master and replica pairs, Sentinel, decoding and exclusions.

## A short tour

The admin index lists each server under **Redis** with a **View** link. There
is no **Add**, because the admin refuses writes:

![The Django admin index with a Redis section listing the Defaults and Sessions servers](https://raw.githubusercontent.com/wolph/django-redis-admin/develop/docs/_static/admin-index.png)

The search box filters on the key. A search for `user` becomes a `*user*`
`SCAN` pattern on the server:

![The key list filtered to a single user:1 hash after searching for user](https://raw.githubusercontent.com/wolph/django-redis-admin/develop/docs/_static/changelist-search.png)

Opening a key shows the raw bytes next to the decoded value, the expiry, the
idle time and whether JSON or base64 decoding applied. The only button is
**Close**:

![The detail page for the json:settings key with the raw value, type, expiry and decoding flags](https://raw.githubusercontent.com/wolph/django-redis-admin/develop/docs/_static/detail-json.png)

A second server gets its own page. Here a `sessions` database shows hashes
with their remaining time to live:

![The Sessions server list with three hashes and their TTL columns](https://raw.githubusercontent.com/wolph/django-redis-admin/develop/docs/_static/changelist-sessions.png)

## Configuration

Everything is optional. The most used settings, with their defaults:

```python
# One admin page per entry. Keys are passed to redis.Redis(), except for
# `master`, `slave`, `service_name`, `meta` and the exclude_* options.
REDIS_SERVERS = {'default': {}}

# Regular expressions matched against the key. Matching values are decoded.
REDIS_JSON_KEY_RE = '^$'
REDIS_BASE64_KEY_RE = '^$'

# Keys to leave out of the admin, for example pickled data from other apps.
REDIS_EXCLUDE_KEY_PREFIXES = ()
REDIS_EXCLUDE_KEY_RE = None
REDIS_EXCLUDE_KEYS = ()

# Values longer than this are cropped in the list view.
REDIS_REPR_CROP_SIZE = 150

# Socket timeout for every connection, in seconds.
REDIS_SOCKET_TIMEOUT = 0.3
```

Master and replica pairs, Sentinel, per-server exclusions and a custom JSON
module are described in the
[configuration reference](https://django-redis-admin.readthedocs.io/en/latest/configuration.html).

> [!NOTE]
> The admin uses `SCAN` with a count matched to the page size, so a page never
> walks the whole keyspace. The total shown at the bottom comes from `INFO
> keyspace`, which is why it can differ from a filtered search count.

## Try the demo

The repository ships a demo project that seeds a local Redis with one key of
every type, including JSON, base64, expiring and excluded examples:

```bash
git clone https://github.com/wolph/django-redis-admin.git
cd django-redis-admin
uv sync
uv run python -m test_redis_admin.demo
```

Log in at <http://127.0.0.1:8080/admin/> with `admin` / `admin`. The demo needs
a Redis on `127.0.0.1:6379`, or set `REDIS_HOST` and `REDIS_PORT` to point it
somewhere else. Every screenshot on this page comes from that demo.

## Development

```bash
uv sync                # package, tests, docs and all checkers
uv run lefthook install
uv run pytest          # tests with the 100% coverage gate
uvx --with tox-uv tox -p auto   # the full matrix CI runs
```

`tox -m check` runs ruff, the three type checkers, codespell, and the
linters for TOML, YAML, Markdown and the GitHub workflows. `tox -m compat`
runs the pinned Django 4.2, 5.2, 6.0 and 6.1 environments and `tox -m
package` builds both distributions and runs the tests from the sdist. CI
runs every one of these as its own job, and a pushed `vX.Y.Z` tag creates
the GitHub release and publishes to PyPI. The
[development guide](https://django-redis-admin.readthedocs.io/en/latest/development.html)
has the details.

## Roadmap

The admin is read-only on purpose: showing a value is safe, saving one back
without knowing its encoding is not. Editing and deleting keys, bitmaps and
HyperLogLogs are the open items. Contributions are welcome through
[GitHub issues](https://github.com/wolph/django-redis-admin/issues).

## Licence

BSD 3-Clause. See [LICENSE](https://github.com/wolph/django-redis-admin/blob/develop/LICENSE).
