# Usage

This guide covers the installation and configuration of `django-redis-admin`.

## Installation

Install `django-redis-admin` with pip:

```bash
pip install django-redis-admin
```

Add `redis_admin` to `INSTALLED_APPS` in your Django settings:

```python
INSTALLED_APPS = [
    ...,
    'redis_admin',
]
```

## Basic Configuration

By default, the admin connects to `localhost:6379`:

```python
REDIS_SERVERS = {
    'localhost': {},
}
```

## Explicit Configuration

To configure a specific host, port, or database number:

```python
REDIS_SERVERS = {
    'redis_server_a': {'host': '127.0.0.1', 'port': 6379, 'db': 0},
}
```

## Master-Slave Configuration

To separate reads and writes between master and slave instances:

```python
REDIS_SERVERS = {
    'redis_server_a': {
        'master': {'host': 'master_hostname', 'port': 6379, 'db': 0},
        'slave': {'host': 'slave_hostname', 'port': 6379, 'db': 0},
    },
}
```

## Sentinel Configuration

For high-availability setups with Redis Sentinel:

```python
REDIS_SENTINELS = [('server_a', 26379), ('server_b', 26379)]
REDIS_SENTINEL_OPTIONS = {'socket_timeout': 0.1}

REDIS_SERVERS = {
    'name_in_admin': {'service_name': 'name_in_sentinel'},
    'other_server': {'service_name': 'other_server'},
}
```

## Base64/JSON Decoding

Values can optionally be decoded from Base64 or JSON using regex patterns matched against keys:

```python
# For all keys
REDIS_JSON_KEY_RE = '.*'
REDIS_BASE64_KEY_RE = '.*'

# Keys starting with a pattern
REDIS_BASE64_KEY_RE = '^some_prefix.*'

# Keys ending with a pattern
REDIS_JSON_KEY_RE = '.*some_suffix$'
```

Custom JSON modules can be specified through `REDIS_JSON_MODULE`:

```python
REDIS_JSON_MODULE = 'json'
```

## Representation Cropping

Within the Django Admin list view, long values are cropped by default:

```python
REDIS_REPR_CROP_SIZE = 150
```

## Excluding Keys From Admin

Exclude specific keys, prefixes, or regex patterns:

```python
# Exclude by prefix (tuple, list, or set of prefixes)
REDIS_EXCLUDE_KEY_PREFIXES = ('constance:', 'session:')

# Exclude by regular expression
REDIS_EXCLUDE_KEY_RE = r'^(constance|session):'

# Exclude specific exact keys
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
