import logging
import itertools
import collections
import redis
import typing
from datetime import timedelta

from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

from . import models
from . import client


logger = logging.getLogger(__name__)


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


class Query:
    order_by = tuple()

    def __init__(self, queryset):
        self.queryset = queryset

    def select_related(self, *args, **kwargs):
        assert not args and not kwargs
        return self


class Queryset:

    def __init__(self, model: models.RedisValue, slice_limit=101):
        self.slice_limit = slice_limit
        self.q: str = '*'
        self.filters: typing.List[Q] = ()
        self.admin = admin
        self.model = model
        self._meta = model._meta
        self.master = client.get_master(model._meta.model_name)
        self.slave = client.get_slave(model._meta.model_name)
        self._cache = None
        self._get_cache = None
        self.slice = None

        self.ordered = True
        self.query = Query(self)

    def count(self):
        return len(self)

    def order_by(self, *args, **kwargs):
        return self

    def filter(self, *filters, **raw_filters):
        self._cache = dict()
        self._get_cache = None
        self.filters = list(filters)
        if raw_filters:
            self.filters.append(Q(**raw_filters))

        query = None
        for filter in self.filters:
            path, args, kwargs = filter.deconstruct()

            error = ('%r is not supported yet, please file a bug report on '
                     'https://github.com/WoLpH/redis_admin/issues/') % filter

            # Not sure when args are ever a thing so we don't support it yet
            # commenting the following line as it causes an issue on Django 3.2.12
            # assert not args, error

            for key, value in kwargs.items():
                # Can't have multiple filters with redis
                assert not query, error

                key = key.split('__', 1)
                if key[1:]:
                    key, query = key
                else:
                    key, = key
                    query = None

                # Can't search for anything besides key with redis
                assert key == 'key', error

                if query == 'exact' or query is None:
                    query = value
                elif query == 'startswith':
                    query = '%s*' % value
                elif query == 'endswith':
                    query = '*%s' % value
                elif query == 'contains':
                    query = '*%s*' % value
                else:
                    raise AssertionError(error)

        self.q = query or '*'

        return self

    def __getattr__(self, key):
        message = 'queryset.%s' % key
        print(message)
        raise AttributeError('Unknown attribute %s' % message)

    def _clone(self):
        return self

    def __len__(self):
        if self.filters:
            # Arbitrary number, we don't want to search if not needed
            if not self._cache:
                self[:self.slice_limit]

            return len(self._cache)
        else:
            keyspace = self.slave.info('keyspace')
            db = self.slave.connection_pool.connection_kwargs.get('db', 0)
            return keyspace.get(f'db{db}', dict()).get('keys', 1000)

    def get(self, *args, **kwargs):
        if not self._get_cache:
            self._get_cache = next(iter(self.filter(**kwargs)))
        return self._get_cache

    def __iter__(self):
        logger.info('searching %r with query %r',
                    self.model._meta.model_name, self.q)

        if self._cache:
            for value in self._cache.values():
                yield value

            return

        self.slice = index = self.slice or slice(self.slice_limit)
        slice_size = min(index.stop, self.slice_limit)
        keys_iter = self.slave.scan_iter(self.q, count=slice_size)
        keys = itertools.islice(keys_iter, index.start, index.stop, index.step)

        keys = [key.decode() for key in keys]

        now = timezone.now()
        with self.slave.pipeline() as pipe:
            for key in keys:
                pipe.type(key)
                pipe.pttl(key)
                pipe.object('IDLETIME', key)

            values = collections.OrderedDict()
            for key, result in zip(keys, grouper(pipe.execute(), 3)):
                type_, ttl, idle = result
                type_ = type_.decode()

                if ttl > 0:
                    expires_at = now + timedelta(seconds=ttl / 1000)
                else:
                    expires_at = None

                if idle > 0:
                    idle_since = now - timedelta(seconds=idle)
                else:
                    idle_since = None

                value = self.model.create(
                    key=key,
                    type=type_,
                    expires_at=expires_at,
                    idle_since=idle_since,
                )
                values[key] = value

        with self.slave.pipeline() as pipe:
            for key in keys:
                value = values[key]
                value.fetch_value(pipe)

            try:
                for key, value in zip(keys, pipe.execute()):
                    values[key].raw_value = value
                    try:
                        values[key].value
                    except Exception as e:
                        logger.exception('Unable to decode: %r, error: %r',
                                         value, e)
            except redis.ResponseError:
                for key in keys:
                    value = values[key]
                    value.raw_value = value.fetch_value(self.slave)

            self._cache = values
            for value in values.values():
                yield value

    def __getitem__(self, index):
        if isinstance(index, int):
            self.index = slice(0, index, 1)
        elif isinstance(index, slice):
            self.index = index
        else:
            raise TypeError('Unsupported index type %r: %r' % (
                type(index), index))

        return self


class RedisAdmin(admin.ModelAdmin):
    show_full_result_count = False
    list_display = ['key', 'type', 'expires_at', 'ttl', 'idle',
                    'cropped_value', 'json', 'base64']
    search_fields = 'key__contains',

    # Keep everything read-only for now, saving isn't implemented yet
    readonly_fields = [f.name for f in models.RedisValue._meta.get_fields()]

    def get_queryset(self, request):
        return Queryset(self.model, self.list_per_page + 1)


for server_model in models.server_models.values():
    admin.site.register(server_model, RedisAdmin)
