import collections
import itertools
import logging
import typing
from datetime import timedelta

import redis
from django.conf import settings as django_settings
from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

from . import client, models, settings

logger: logging.Logger = logging.getLogger(__name__)


def grouper(
    iterable: typing.Iterable[typing.Any],
    n: int,
    fillvalue: typing.Any = None,
) -> typing.Iterator[typing.Any]:
    args: list[typing.Iterator[typing.Any]] = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


class Query:
    order_by: typing.ClassVar[tuple[typing.Any, ...]] = ()

    def __init__(self, queryset: typing.Any) -> None:
        self.queryset: typing.Any = queryset

    def select_related(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> 'Query':
        assert not args and not kwargs
        return self


class Queryset:
    def __init__(
        self, model: models.RedisValue, slice_limit: int = 101
    ) -> None:
        self.slice_limit: int = slice_limit
        self.q: str = '*'
        self.filters: list[Q] = []
        self.admin: typing.Any = admin
        self.model: models.RedisValue = model
        self._meta: typing.Any = model._meta
        self.master: redis.Redis = client.get_master(model._meta.model_name)
        self.slave: redis.Redis = client.get_slave(model._meta.model_name)
        self._cache: dict[str, typing.Any] | None = None
        self._get_cache: typing.Any = None
        self.slice: slice | None = None

        meta_prefixes: tuple[str, ...] = settings._get_exclude_key_prefixes(
            getattr(self._meta, 'exclude_key_prefixes', ())
        )
        meta_re: typing.Pattern | None = settings._get_exclude_key_re(
            getattr(self._meta, 'exclude_key_re', None)
        )
        meta_keys: set[str] = settings._get_exclude_keys(
            getattr(self._meta, 'exclude_keys', ())
        )

        global_prefixes: tuple[str, ...] = settings._get_exclude_key_prefixes(
            getattr(
                django_settings,
                'REDIS_EXCLUDE_KEY_PREFIXES',
                getattr(settings, 'EXCLUDE_KEY_PREFIXES', ()),
            )
        )
        global_re: typing.Pattern | None = settings._get_exclude_key_re(
            getattr(
                django_settings,
                'REDIS_EXCLUDE_KEY_RE',
                getattr(settings, 'EXCLUDE_KEY_RE', None),
            )
        )
        global_keys: set[str] = settings._get_exclude_keys(
            getattr(
                django_settings,
                'REDIS_EXCLUDE_KEYS',
                getattr(settings, 'EXCLUDE_KEYS', ()),
            )
        )

        self.exclude_key_prefixes: tuple[str, ...] = tuple(
            sorted(set(meta_prefixes + global_prefixes))
        )
        self.exclude_keys: set[str] = meta_keys | global_keys
        self.exclude_key_res: list[typing.Pattern] = [
            pattern for pattern in (meta_re, global_re) if pattern is not None
        ]
        self.exclude_key_re: typing.Pattern | None = (
            self.exclude_key_res[0] if self.exclude_key_res else None
        )

        self.ordered: bool = True
        self.query: Query = Query(self)

    def is_excluded(self, key: str) -> bool:
        if self.exclude_keys and key in self.exclude_keys:
            return True
        if self.exclude_key_prefixes and key.startswith(
            self.exclude_key_prefixes
        ):
            return True
        if self.exclude_key_res:
            for pattern in self.exclude_key_res:
                if pattern.search(key):
                    return True
        return False

    def count(self) -> int:
        return len(self)

    def order_by(self, *args: typing.Any, **kwargs: typing.Any) -> 'Queryset':
        return self

    def filter(self, *filters: Q, **raw_filters: typing.Any) -> 'Queryset':
        self._cache = {}
        self._get_cache = None
        self.filters = list(filters)
        if raw_filters:
            self.filters.append(Q(**raw_filters))

        query: str | None = None
        for filter_item in self.filters:
            _, args, _ = filter_item.deconstruct()

            error: str = (
                f'{filter_item!r} is not supported yet, please file a bug '
                'report on https://github.com/WoLpH/redis_admin/issues/'
            )

            # Not sure when args are ever a thing so we don't support it yet
            # Commenting out as it causes an issue on Django 3.2.12
            # assert not args, error

            for key, value in args:
                # Can't have multiple filters with redis
                assert not query, error

                key_parts: list[str] = key.split('__', 1)
                if key_parts[1:]:
                    lookup: str | None = key_parts[1]
                else:
                    lookup = None
                filter_key: str = key_parts[0]

                # Can't search for anything besides key with redis
                assert filter_key == 'key', error

                if lookup == 'exact' or lookup is None:
                    query = value
                elif lookup == 'startswith':
                    query = f'{value}*'
                elif lookup == 'endswith':
                    query = f'*{value}'
                elif lookup == 'contains':
                    query = f'*{value}*'
                else:
                    raise AssertionError(error)

        self.q = query or '*'

        return self

    def __getattr__(self, key: str) -> typing.Any:
        message: str = f'queryset.{key}'
        raise AttributeError(f'Unknown attribute {message}')

    def _clone(self) -> 'Queryset':
        return self

    def __len__(self) -> int:
        if self.filters:
            # Arbitrary number, we don't want to search if not needed
            if not self._cache:
                self[: self.slice_limit]

            return len(self._cache) if self._cache is not None else 0

        keyspace: dict[str, typing.Any] = self.slave.info('keyspace')
        db: int = self.slave.connection_pool.connection_kwargs.get('db', 0)
        return keyspace.get(f'db{db}', {}).get('keys', 1000)

    def get(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        self._get_cache = None
        try:
            self._get_cache = next(iter(self.filter(**kwargs)))
        except StopIteration as exc:
            object_name: str = self.model._meta.object_name
            raise self.model.DoesNotExist(
                f'{object_name} matching query does not exist.'
            ) from exc
        return self._get_cache

    def _get_keys(self) -> list[str]:
        self.slice = index = self.slice or slice(self.slice_limit)
        slice_size: int = (
            min(index.stop, self.slice_limit)
            if index.stop is not None
            else self.slice_limit
        )
        raw_keys_iter: typing.Iterator[typing.Any] = self.slave.scan_iter(
            self.q, count=slice_size
        )
        decoded_keys_iter: typing.Iterator[str] = (
            models.decode_bytes(k) for k in raw_keys_iter
        )
        filtered_keys_iter: typing.Iterator[str] = (
            k for k in decoded_keys_iter if not self.is_excluded(k)
        )
        return list(
            itertools.islice(
                filtered_keys_iter, index.start, index.stop, index.step
            )
        )

    def _fetch_metadata(
        self, keys: list[str]
    ) -> collections.OrderedDict[str, typing.Any]:
        now: timezone.datetime = timezone.now()
        with self.slave.pipeline() as pipe:
            for key in keys:
                pipe.type(key)
                pipe.pttl(key)
                pipe.object('IDLETIME', key)

            values: collections.OrderedDict[str, typing.Any] = (
                collections.OrderedDict()
            )
            for key, result in zip(
                keys, grouper(pipe.execute(), 3), strict=True
            ):
                type_, ttl, idle = result
                type_ = type_.decode()

                expires_at: timezone.datetime | None = (
                    now + timedelta(seconds=ttl / 1000) if ttl > 0 else None
                )
                idle_since: timezone.datetime | None = (
                    now - timedelta(seconds=idle) if idle > 0 else None
                )

                value: models.RedisValue = self.model.create(
                    key=key,
                    type=type_,
                    expires_at=expires_at,
                    idle_since=idle_since,
                )
                values[key] = value

        return values

    def _fetch_values(
        self,
        keys: list[str],
        values: collections.OrderedDict[str, typing.Any],
    ) -> None:
        with self.slave.pipeline() as pipe:
            for key in keys:
                model_value: models.RedisValue = values[key]
                model_value.fetch_value(pipe)

            try:
                for key, raw_val in zip(keys, pipe.execute(), strict=True):
                    values[key].raw_value = raw_val
                    try:
                        _ = values[key].value
                    except Exception:
                        logger.exception('Unable to decode: %r', raw_val)
            except redis.ResponseError:
                for key in keys:
                    model_value = values[key]
                    model_value.raw_value = model_value.fetch_value(self.slave)

    def __iter__(self) -> typing.Iterator[typing.Any]:
        logger.info(
            'searching %r with query %r', self.model._meta.model_name, self.q
        )

        if self._cache:
            for value in self._cache.values():
                yield value
            return

        keys: list[str] = self._get_keys()
        values: collections.OrderedDict[str, typing.Any] = (
            self._fetch_metadata(keys)
        )
        self._fetch_values(keys, values)

        self._cache = values
        for value in values.values():
            yield value

    def __getitem__(self, index: int | slice) -> 'Queryset':
        if isinstance(index, int):
            self.slice = slice(index, index + 1, 1)
        elif isinstance(index, slice):
            self.slice = index
        else:
            raise TypeError(
                f'Unsupported index type {type(index)!r}: {index!r}'
            )

        return self


class RedisAdmin(admin.ModelAdmin):
    show_full_result_count: bool = False
    list_display: typing.ClassVar[list[str]] = [
        'key',
        'type',
        'expires_at',
        'ttl',
        'idle',
        'cropped_value',
        'json',
        'base64',
    ]
    search_fields: typing.ClassVar[tuple[str, ...]] = ('key__contains',)

    # Keep everything read-only for now, saving isn't implemented yet
    readonly_fields: typing.ClassVar[list[str]] = [
        f.name for f in models.RedisValue._meta.get_fields()
    ]

    def get_queryset(self, request: typing.Any) -> Queryset:
        return Queryset(self.model, self.list_per_page + 1)


for server_model in models.server_models.values():
    admin.site.register(server_model, RedisAdmin)
