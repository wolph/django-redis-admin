==============================================================================
Django Redis Admin
==============================================================================

Travis status:

.. image:: https://travis-ci.org/WoLpH/django-redis-admin.svg?branch=master
  :target: https://travis-ci.org/WoLpH/django-redis-admin

Introduction
==============================================================================

With `django-redis-admin` you can view (and in the future, edit) your Redis 
databases. It supports simple servers, master slave setups and sentinel setups.

The admin works by creating a `RedisQueryset` which fakes Django models and 
querysets so the `ModelAdmin` thinks it's using a regular database backed model.

Requirements
==============================================================================

* Python `3.6` and above
* Django (tested with 2.1, probably works with any version that supports
  Python 3)
* Python-redis (`pip install redis`)

Installation
==============================================================================

`django-redis-admin` can be installed via pip.

.. code-block:: bash

    pip install django-redis-admin

Then just add `redis_admin` to your `INSTALLED_APPS`.

Optionally, configure your servers if you have multiple and/or non-standard 
(i.e. non-localhost) redis servers.

Below are several example configurations. The default settings can always be
found in `redis_admin/settings.py`

You can run the demo project using the following commands:

.. code-block:: bash

    cd test_redis_admin
    python manage.py runserver

The default username/password is `admin`/`admin`: http://localhost:8080/admin/

Basic configuration
------------------------------------------------------------------------------

.. code-block:: python

    # https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
    REDIS_SERVERS = dict(
        localhost=dict(),
    )

Explicit configuration
------------------------------------------------------------------------------

.. code-block:: python

   # https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
   REDIS_SERVERS = dict(
       redis_server_a=dict(host='127.0.0.1', port=6379, db=0),
   )

Master slave configuration
------------------------------------------------------------------------------

.. code-block:: python

   # https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
   REDIS_SERVERS = dict(
       redis_server_a=dict(
       	 master=dict(host='master_hostname', port=6379, db=0),
       	 slave=dict(host='slave_hostname', port=6379, db=0),
      )
   )

Sentinel Configuration
------------------------------------------------------------------------------

.. code-block:: python

   # The `REDIS_SENTINELS` setting should be a list containing host/port
   # combinations. As documented here:
   # https://github.com/andymccurdy/redis-py/blob/master/README.rst#sentinel-support
   REDIS_SENTINELS = [('server_a', 26379), ('server_b', 26379)]

   # The `REDIS_SENTINEL_OPTIONS` are the extra arguments to
   # `redis.sentinel.Sentinel`:
   # https://github.com/andymccurdy/redis-py/blob/cdfe2befbe00db4a3c48c9ddd6d64dea15f6f0db/redis/sentinel.py#L128-L155
   REDIS_SENTINEL_OPTIONS = dict(socket_timeout=0.1)

   # The `service_name` is used to find the server within the Sentinel
   # configuration. The dictionary key will be used as the name in the admin
   # https://redis-py.readthedocs.io/en/latest/index.html#redis.Redis
   REDIS_SERVERS = dict(
        name_in_admin=dict(service_name='name_in_sentinel'),
        other_server=dict(service_name='other_server'),
   )

Base64 and/or JSON decoding
------------------------------------------------------------------------------

As a convenient option all values can optionally be `base64` and/or `json`
encoded. To configure this a regular expression can be specified which will be
matched against the keys.

.. code-block:: python

   # For all keys
   REDIS_JSON_KEY_RE = '.*'
   REDIS_BASE64_KEY_RE = '.*'

   # Keys starting with a pattern:
   REDIS_BASE64_KEY_RE = '^some_prefix.*'

   # Keys ending with a pattern:
   REDIS_JSON_KEY_RE = '.*some_suffix$'

And if a specific `json` decoder is needed, the `json` module can be specified.
The module needs to be importable and have a `dumps` and `loads` method. By
default it simply imports the `json` module:

.. code-block:: python

   REDIS_JSON_MODULE = 'json'

Representation cropping
------------------------------------------------------------------------------

Within the Django Admin list view the values are cropped by default to prevent really long lines. This size can be adjusted through:

.. code-block:: python

   REDIS_REPR_CROP_SIZE = 150

TODO
==============================================================================

- Allow saving values
- Allow deleting values
- Support Redis Bitmaps
- Support Redis HyperLogLogs

