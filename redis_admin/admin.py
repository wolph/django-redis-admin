# pyright: reportPrivateUsage=false
from __future__ import annotations

import collections
import itertools
import logging
import re
import typing
from datetime import datetime, timedelta

import redis
from django.conf import settings as django_settings
from django.contrib import admin
from django.db.models import Q
from django.http import HttpRequest
from django.utils import timezone

from . import client, models, settings

logger: logging.Logger = logging.getLogger(__name__)


def grouper(
    iterable: typing.Iterable[typing.Any],
    n: int,
    fillvalue: typing.Any = None,
) -> typing.Iterator[tuple[typing.Any, ...]]:
    args: list[typing.Iterator[typing.Any]] = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def _extract_q_pairs(
    items: typing.Iterable[typing.Any],
) -> list[tuple[str, typing.Any]]:
    pairs: list[tuple[str, typing.Any]] = []
    for item in items:
        if isinstance(item, Q):
            pairs.extend(_extract_q_pairs(item.children))
        elif isinstance(item, (tuple, list)):
            item_any: typing.Any = item  # pyright: ignore[reportUnknownVariableType]
            if len(item_any) == 2 and isinstance(item_any[0], str):  # pyright: ignore[reportUnknownArgumentType]
                pairs.append((str(item_any[0]), item_any[1]))  # pyright: ignore[reportUnknownArgumentType]
    return pairs


class Query:
    order_by: typing.ClassVar[tuple[typing.Any, ...]] = ()

    def __init__(self, queryset: Queryset) -> None:
        self.queryset: Queryset = queryset

    def select_related(self, *args: typing.Any, **kwargs: typing.Any) -> Query:
        assert not args
        assert not kwargs
        return self


class Queryset:
    def __init__(
        self, model: type[models.RedisValue], slice_limit: int = 101
    ) -> None:
        self.slice_limit: int = slice_limit
        self.q: str = '*'
        self.filters: list[Q] = []
        self.admin: typing.Any = admin
        self.model: type[models.RedisValue] = model
        self._meta: typing.Any = model._meta
        model_name: str = str(getattr(self._meta, 'model_name', None) or '')
        self.master: redis.Redis[bytes] = client.get_master(model_name)
        self.slave: redis.Redis[bytes] = client.get_slave(model_name)
        self._cache: collections.OrderedDict[str, models.RedisValue] | None = (
            None
        )
        self._get_cache: models.RedisValue | None = None
        self.slice: slice | None = None

        meta_prefixes: tuple[str, ...] = settings.get_exclude_key_prefixes(
            getattr(self._meta, 'exclude_key_prefixes', ())
        )
        meta_re: re.Pattern[str] | None = settings.get_exclude_key_re(
            getattr(self._meta, 'exclude_key_re', None)
        )
        meta_keys: set[str] = settings.get_exclude_keys(
            getattr(self._meta, 'exclude_keys', ())
        )

        global_prefixes: tuple[str, ...] = settings.get_exclude_key_prefixes(
            getattr(
                django_settings,
                'REDIS_EXCLUDE_KEY_PREFIXES',
                getattr(settings, 'EXCLUDE_KEY_PREFIXES', ()),
            )
        )
        global_re: re.Pattern[str] | None = settings.get_exclude_key_re(
            getattr(
                django_settings,
                'REDIS_EXCLUDE_KEY_RE',
                getattr(settings, 'EXCLUDE_KEY_RE', None),
            )
        )
        global_keys: set[str] = settings.get_exclude_keys(
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
        self.exclude_key_res: list[re.Pattern[str]] = [
            pattern for pattern in (meta_re, global_re) if pattern is not None
        ]
        self.exclude_key_re: re.Pattern[str] | None = (
            self.exclude_key_res[0] if self.exclude_key_res else None
        )

        self.ordered: bool = True
        self.totally_ordered: bool = True
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

    def order_by(self, *args: typing.Any, **kwargs: typing.Any) -> Queryset:
        return self

    def filter(self, *filters: Q, **raw_filters: typing.Any) -> Queryset:
        self._cache = None
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

            filter_pairs: list[tuple[str, typing.Any]] = _extract_q_pairs(args)

            for key, value in filter_pairs:
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

    def _clone(self) -> Queryset:
        return self

    def __len__(self) -> int:
        if self.filters:
            # Arbitrary number, we don't want to search if not needed
            if not self._cache:
                list(iter(self[: self.slice_limit]))

            return len(self._cache) if self._cache is not None else 0

        keyspace: typing.Mapping[str, typing.Any] = self.slave.info('keyspace')
        db: int = int(
            self.slave.connection_pool.connection_kwargs.get('db', 0)
        )
        db_key: str = f'db{db}'
        if db_key in keyspace:
            raw_info: object = keyspace[db_key]
            if isinstance(raw_info, dict):
                info_dict: dict[str, object] = typing.cast(
                    dict[str, object], raw_info
                )
                keys_val: object = info_dict.get('keys')
                if isinstance(keys_val, (int, str)):
                    return int(keys_val)
        return 1000

    def get(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> models.RedisValue:
        self._get_cache = None
        try:
            self._get_cache = next(iter(self.filter(**kwargs)))
        except StopIteration as exc:
            meta_obj: typing.Any = getattr(self.model, '_meta', None)
            object_name: str = str(
                getattr(meta_obj, 'object_name', None) or 'RedisValue'
            )
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
            str(models.decode_bytes(k)) for k in raw_keys_iter
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
    ) -> collections.OrderedDict[str, models.RedisValue]:
        now: datetime = timezone.now()
        with self.slave.pipeline() as pipe:
            p: typing.Any = pipe
            for key in keys:
                p.type(key)
                p.pttl(key)
                p.object('IDLETIME', key)

            values: collections.OrderedDict[str, models.RedisValue] = (
                collections.OrderedDict()
            )
            for key, result in zip(
                keys, grouper(pipe.execute(), 3), strict=True
            ):
                type_, ttl, idle = result
                decoded_type: str = str(models.decode_bytes(type_))
                if decoded_type == 'none':
                    continue

                expires_at: datetime | None = (
                    now + timedelta(seconds=ttl / 1000)
                    if ttl is not None and ttl > 0
                    else None
                )
                idle_since: datetime | None = (
                    now - timedelta(seconds=idle)
                    if idle is not None and idle > 0
                    else None
                )

                value: models.RedisValue = self.model.create(
                    key=key,
                    type=decoded_type,
                    expires_at=expires_at,
                    idle_since=idle_since,
                )
                values[key] = value

        return values

    def _fetch_values(
        self,
        keys: list[str],
        values: collections.OrderedDict[str, models.RedisValue],
    ) -> None:
        fetch_keys: list[str] = [k for k in keys if k in values]
        with self.slave.pipeline() as pipe:
            for key in fetch_keys:
                model_value: models.RedisValue = values[key]
                model_value.fetch_value(pipe)

            try:
                results: list[typing.Any] = pipe.execute()
                for key, raw_val in zip(fetch_keys, results, strict=True):
                    values[key].raw_value = raw_val
                    try:
                        _ = values[key].value
                    except Exception:
                        logger.exception('Unable to decode: %r', raw_val)
            except redis.ResponseError:
                for key in fetch_keys:
                    model_value = values[key]
                    model_value.raw_value = model_value.fetch_value(self.slave)

    def __iter__(self) -> typing.Iterator[models.RedisValue]:
        meta_obj: typing.Any = getattr(self.model, '_meta', None)
        model_name: str = str(getattr(meta_obj, 'model_name', None) or '')
        logger.info('searching %r with query %r', model_name, self.q)

        if self._cache is not None:
            for value in self._cache.values():
                yield value
            return

        keys: list[str] = self._get_keys()
        values: collections.OrderedDict[str, models.RedisValue] = (
            self._fetch_metadata(keys)
        )
        self._fetch_values(list(values.keys()), values)

        self._cache = values
        for value in values.values():
            yield value

    def __getitem__(self, index: int | slice) -> Queryset:
        if isinstance(index, int):
            self.slice = slice(index, index + 1, 1)
        elif type(index) is slice:
            self.slice = index
        else:
            raise TypeError(
                f'Unsupported index type {type(index)!r}: {index!r}'
            )

        return self


if typing.TYPE_CHECKING:
    _ModelAdminBase = admin.ModelAdmin[models.RedisValue]
else:
    _ModelAdminBase = admin.ModelAdmin


class RedisAdmin(_ModelAdminBase):
    show_full_result_count: typing.ClassVar[bool] = False
    list_display: (
        list[typing.Callable[[models.RedisValue], str | bool] | str]
        | tuple[typing.Callable[[models.RedisValue], str | bool] | str, ...]
    ) = (
        'key',
        'type',
        'expires_at',
        'ttl',
        'idle',
        'cropped_value',
        'json',
        'base64',
    )
    search_fields: typing.ClassVar[list[str] | tuple[str, ...]] = (
        'key__contains',
    )

    # Keep everything read-only for now, saving isn't implemented yet
    readonly_fields: typing.ClassVar[list[str] | tuple[str, ...]] = tuple(
        f.name for f in models.RedisValue._meta.get_fields()
    )

    def get_queryset(self, request: HttpRequest) -> typing.Any:
        return Queryset(self.model, self.list_per_page + 1)


for server_model in models.server_models.values():
    admin.site.register(server_model, RedisAdmin)
