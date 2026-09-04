# Django Redis Admin

## Introduction

With `django-redis-admin` you can view (and in the future, edit) your Redis databases. It supports simple servers, master-slave setups, and sentinel setups.

The admin works by creating a `RedisQueryset` which fakes Django models and querysets so the `ModelAdmin` thinks it is using a regular database backed model.

Since Redis only supports basic types the library allows for optional `base64` encoding/decoding and `json` encoding/decoding.

Do not use this library as a regular queryset to access Redis. In addition to querying data it executes extra queries that you usually do not need (such as fetching idle data) and performs automatic conversion steps.

## Requirements

- Python 3.10 and above
- Django 4.2 and above
- Redis (`redis>=4.0.0`)

## Installation

`django-redis-admin` can be installed via pip:

```bash
pip install django-redis-admin
```

Then add `redis_admin` to your `INSTALLED_APPS`.

Optionally, configure your servers if you have multiple or non-standard (non-localhost) Redis servers.

Below are several example configurations. The default settings can always be found in `redis_admin/settings.py`.

You can run the demo project using the following commands:

```bash
cd test_redis_admin
python manage.py runserver
```

The default username and password is `admin`/`admin`: http://localhost:8080/admin/

### Basic Configuration

```python
# https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
REDIS_SERVERS = {
    'localhost': {},
}
```

### Explicit Configuration

```python
# https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
REDIS_SERVERS = {
    'redis_server_a': {'host': '127.0.0.1', 'port': 6379, 'db': 0},
}
```

### Master-Slave Configuration

```python
# https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
REDIS_SERVERS = {
    'redis_server_a': {
        'master': {'host': 'master_hostname', 'port': 6379, 'db': 0},
        'slave': {'host': 'slave_hostname', 'port': 6379, 'db': 0},
    },
}
```

### Sentinel Configuration

```python
# The `REDIS_SENTINELS` setting should be a list containing host/port combinations:
REDIS_SENTINELS = [('server_a', 26379), ('server_b', 26379)]

# The `REDIS_SENTINEL_OPTIONS` are extra arguments to `redis.sentinel.Sentinel`:
REDIS_SENTINEL_OPTIONS = {'socket_timeout': 0.1}

# The `service_name` is used to find the server within the Sentinel configuration:
REDIS_SERVERS = {
    'name_in_admin': {'service_name': 'name_in_sentinel'},
    'other_server': {'service_name': 'other_server'},
}
```

### Base64/JSON Decoding

As a convenient option all values can optionally be `base64` or `json` encoded. To configure this a regular expression can be specified which will be matched against the keys.

```python
# For all keys
REDIS_JSON_KEY_RE = '.*'
REDIS_BASE64_KEY_RE = '.*'

# Keys starting with a pattern:
REDIS_BASE64_KEY_RE = '^some_prefix.*'

# Keys ending with a pattern:
REDIS_JSON_KEY_RE = '.*some_suffix$'
```

When a specific JSON decoder is needed, specify the module name in `REDIS_JSON_MODULE`. The module must be importable and provide `dumps` and `loads` functions. By default it imports the standard library `json` module:

```python
REDIS_JSON_MODULE = 'json'
```

### Representation Cropping

Within the Django Admin list view the values are cropped by default to prevent long lines. This size can be adjusted through:

```python
REDIS_REPR_CROP_SIZE = 150
```

### Excluding Keys From Admin

You can exclude specific keys, key prefixes, or regex patterns from appearing in the admin. This is useful for third-party libraries such as django-constance, sessions, or cache entries that store pickled or unparsable data in Redis:

```python
# Exclude by prefix (tuple, list, or set of prefixes):
REDIS_EXCLUDE_KEY_PREFIXES = ('constance:', 'session:')

# Exclude by regular expression:
REDIS_EXCLUDE_KEY_RE = r'^(constance|session):'

# Exclude specific exact keys:
REDIS_EXCLUDE_KEYS = ('secret_token', 'internal_counter')
```

Exclusions can also be configured per server in `REDIS_SERVERS`:

```python
REDIS_SERVERS = {
    'default': {
        'host': '127.0.0.1',
        'port': 6379,
        'exclude_key_prefixes': ('constance:',),
    },
}
```

## TODO

- Allow saving values
- Allow deleting values
- Support Redis Bitmaps
- Support Redis HyperLogLogs
