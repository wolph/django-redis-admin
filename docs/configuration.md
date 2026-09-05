# Configuration

Every setting is optional and lives in your Django settings module. The
defaults are collected at the end of the page.

## Servers

`REDIS_SERVERS` maps a name to a connection. Each entry becomes one admin
page, and the name becomes the page label unless a `meta` dictionary says
otherwise.

### A single server

An empty dictionary connects to `localhost:6379`, database `0`:

```python
REDIS_SERVERS = {
    'default': {},
}
```

Anything else in the dictionary is passed to `redis.Redis()`, so `host`,
`port`, `db`, `password`, `ssl` and every other client option work here:

```python
REDIS_SERVERS = {
    'cache': {'host': '127.0.0.1', 'port': 6379, 'db': 1},
}
```

### A master and a replica

When reads should go to a replica, split the entry into `master` and `slave`
dictionaries. The admin reads from the replica and keeps the master for the
day writing lands:

```python
REDIS_SERVERS = {
    'cache': {
        'master': {'host': 'master.internal', 'port': 6379, 'db': 0},
        'slave': {'host': 'replica.internal', 'port': 6379, 'db': 0},
    },
}
```

### Sentinel

With Sentinel the admin asks the sentinels for the current master and a
replica instead of connecting to fixed hosts. List the sentinels once, then
give each server the `service_name` it is registered under:

```python
REDIS_SENTINELS = [('sentinel-a', 26379), ('sentinel-b', 26379)]
REDIS_SENTINEL_OPTIONS = {'socket_timeout': 0.1}

REDIS_SERVERS = {
    'cache': {'service_name': 'cache'},
    'sessions': {'service_name': 'sessions'},
}
```

`REDIS_SENTINEL_OPTIONS` is passed to `redis.sentinel.Sentinel()` and defaults
to the socket timeout below.

### Labels and per-server options

A `meta` dictionary sets attributes on the generated model's `Meta`, which is
how you rename the admin page:

```python
REDIS_SERVERS = {
    'sessions': {
        'db': 2,
        'meta': {
            'verbose_name': 'session',
            'verbose_name_plural': 'sessions',
        },
    },
}
```

The exclusion options from the next section are also accepted per server.
`meta`, `master`, `slave`, `service_name` and the `exclude_*` keys are
removed before the rest reaches the Redis client.

## Excluding keys

Other libraries store data in the same Redis, and not all of it is fit to
show. django-constance writes pickles, session backends write opaque blobs.
Three settings keep such keys out of the admin, and all three accept a single
string as well as a collection:

```python
# Keys starting with any of these prefixes.
REDIS_EXCLUDE_KEY_PREFIXES = ('constance:', 'session:')

# Keys matching a regular expression, as a string or a compiled pattern.
REDIS_EXCLUDE_KEY_RE = r'^(constance|session):'

# Exact keys.
REDIS_EXCLUDE_KEYS = ('secret_token', 'internal_counter')
```

The same options work inside a `REDIS_SERVERS` entry and are combined with the
global settings:

```python
REDIS_SERVERS = {
    'default': {
        'exclude_key_prefixes': ('constance:',),
    },
}
```

Excluded keys are filtered after `SCAN` returns them, so they still count
towards the total from `INFO keyspace`.

## Decoding values

Redis stores bytes. The admin decodes them as UTF-8 and, for keys that match a
pattern, goes one step further:

```python
# Decode matching values from base64 first.
REDIS_BASE64_KEY_RE = r'^base64:'

# Then parse matching values as JSON.
REDIS_JSON_KEY_RE = r'^json:'
```

Both default to `'^$'`, which matches nothing. Use `'.*'` to decode every key.
When a value refuses to decode, the admin shows the undecoded value and marks
the flag in the list with a red cross rather than hiding the key.

A different JSON implementation can be swapped in by module name. The module
needs `loads` and `dumps` functions:

```python
REDIS_JSON_MODULE = 'orjson'
```

## Display and timeouts

Long values are cropped in the list view, keeping the start and the end:

```python
REDIS_REPR_CROP_SIZE = 150
```

Every connection gets a socket timeout so an unreachable server produces an
error page instead of a hanging admin. It applies to plain servers, master
and replica pairs and Sentinel alike:

```python
REDIS_SOCKET_TIMEOUT = 0.3
```

```{tip}
Raise `REDIS_SOCKET_TIMEOUT` for servers on the far side of a slow link. The
admin issues one `SCAN` plus a pipeline per page, so a timeout that is too
tight shows up as intermittent errors rather than slow pages.
```

## Defaults

```python
REDIS_SERVERS = {'default': {}}
REDIS_SENTINELS = []
REDIS_SENTINEL_OPTIONS = {}
REDIS_SOCKET_TIMEOUT = 0.3
REDIS_JSON_KEY_RE = '^$'
REDIS_BASE64_KEY_RE = '^$'
REDIS_JSON_MODULE = 'json'
REDIS_REPR_CROP_SIZE = 150
REDIS_EXCLUDE_KEY_PREFIXES = ()
REDIS_EXCLUDE_KEY_RE = None
REDIS_EXCLUDE_KEYS = ()
```

The values are read once, when `redis_admin.settings` is imported, so a
settings change needs a server restart.
