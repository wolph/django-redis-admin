# pyright: reportPrivateUsage=false
from __future__ import annotations

import collections
import typing
from unittest import mock

import pytest
import redis
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.db.models import Q
from django.test import RequestFactory

from redis_admin import admin, models


def test_grouper() -> None:
    result: list[tuple[typing.Any, ...]] = list(
        admin.grouper([1, 2, 3, 4, 5], 2, fillvalue='fill')
    )
    assert result == [(1, 2), (3, 4), (5, 'fill')]


def test_extract_q_pairs() -> None:
    unsupported: list[typing.Any] = [
        None,
        123,
        (),
        ('too', 'many', 'items'),
        (1, 2),
    ]
    assert admin._extract_q_pairs(unsupported) == []
    nested_q: Q = Q(Q(key__contains='find_me'))
    assert admin._extract_q_pairs([nested_q]) == [('key__contains', 'find_me')]


def test_query_select_related() -> None:
    qs: admin.Queryset = admin.Queryset(models.Default)
    query: admin.Query = admin.Query(qs)
    assert query.order_by == ()
    assert query.select_related() is query

    with pytest.raises(AssertionError):
        query.select_related('arg')

    with pytest.raises(AssertionError):
        query.select_related(kwarg='val')


def test_queryset_count_and_len_without_filters(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    qs: admin.Queryset = admin.Queryset(models.Default)

    def mock_info_42(_section: str | None = None) -> dict[str, typing.Any]:
        return {'db0': {'keys': 42}}

    monkeypatch.setattr(qs.slave, 'info', mock_info_42)
    assert len(qs) == 42
    assert qs.count() == 42

    def mock_info_55(_section: str | None = None) -> dict[str, typing.Any]:
        return {'db0': {'keys': '55'}}

    monkeypatch.setattr(qs.slave, 'info', mock_info_55)
    assert len(qs) == 55

    def mock_info_none(_section: str | None = None) -> dict[str, typing.Any]:
        return {'db0': {'keys': None}}

    monkeypatch.setattr(qs.slave, 'info', mock_info_none)
    assert len(qs) == 1000

    def mock_info_str(_section: str | None = None) -> dict[str, typing.Any]:
        return {'db0': 'not_dict'}

    monkeypatch.setattr(qs.slave, 'info', mock_info_str)
    assert len(qs) == 1000

    def mock_info_empty(_section: str | None = None) -> dict[str, typing.Any]:
        return {}

    monkeypatch.setattr(qs.slave, 'info', mock_info_empty)
    assert len(qs) == 1000


def test_queryset_len_with_filters(redis_client: redis.Redis[bytes]) -> None:
    redis_client.set('filter_key_1', 'val1')
    redis_client.set('filter_key_2', 'val2')
    redis_client.set('other_key', 'val3')

    qs: admin.Queryset = admin.Queryset(models.Default)
    qs_filtered: admin.Queryset = qs.filter(key__startswith='filter_key')

    assert qs_filtered._cache is None
    count_result: int = len(qs_filtered)
    assert count_result == 2
    assert qs_filtered._cache is not None

    cached_count: int = len(qs_filtered)
    assert cached_count == 2

    with mock.patch.object(admin.Queryset, '__iter__', return_value=iter([])):
        qs_filtered._cache = None
        assert qs_filtered.__len__() == 0


def test_queryset_filter_lookups(redis_client: redis.Redis[bytes]) -> None:
    qs: admin.Queryset = admin.Queryset(models.Default)

    qs.filter(key='exact_val')
    assert qs.q == 'exact_val'

    qs.filter(key__exact='exact_val2')
    assert qs.q == 'exact_val2'

    qs.filter(key__startswith='prefix')
    assert qs.q == 'prefix*'

    qs.filter(key__endswith='suffix')
    assert qs.q == '*suffix'

    qs.filter(key__contains='middle')
    assert qs.q == '*middle*'

    qs.filter()
    assert qs.q == '*'

    qs_q: admin.Queryset = admin.Queryset(models.Default)
    qs_q.filter(Q(key='val_from_q'))
    assert qs_q.q == 'val_from_q'

    with pytest.raises(AssertionError):
        admin.Queryset(models.Default).filter(key__gt='unsupported')

    with pytest.raises(AssertionError):
        admin.Queryset(models.Default).filter(not_key='value')

    with pytest.raises(AssertionError):
        admin.Queryset(models.Default).filter(
            key='first', key__startswith='sec'
        )

    with pytest.raises(AssertionError):
        admin.Queryset(models.Default).filter(Q(key='q1'), Q(key='q2'))


def test_queryset_order_by_clone_and_getattr() -> None:
    qs: admin.Queryset = admin.Queryset(models.Default)
    assert qs.order_by('key') is qs
    assert qs._clone() is qs

    with pytest.raises(
        AttributeError, match=r'Unknown attribute queryset\.unsupported_attr'
    ):
        _ = qs.unsupported_attr


def test_queryset_getitem() -> None:
    qs: admin.Queryset = admin.Queryset(models.Default)

    indexed: admin.Queryset = qs[5]
    assert indexed.slice == slice(5, 6, 1)

    sliced: admin.Queryset = qs[2:10]
    assert sliced.slice == slice(2, 10, None)

    with pytest.raises(TypeError, match='Unsupported index type'):
        _ = qs['invalid_index']  # type: ignore[index]


def test_queryset_get(redis_client: redis.Redis[bytes]) -> None:
    redis_client.set('target_key', 'hello_redis')

    qs: admin.Queryset = admin.Queryset(models.Default)
    item: models.RedisValue = qs.get(key='target_key')
    assert item.key == 'target_key'
    assert qs._get_cache is item

    with pytest.raises(
        models.Default.DoesNotExist,
        match=r'Default matching query does not exist\.',
    ):
        qs.get(key='missing_key')

    class FakeMeta:
        object_name: str | None = None
        model_name: str | None = None
        exclude_key_prefixes: tuple[str, ...] = ()
        exclude_key_re: None = None
        exclude_keys: typing.ClassVar[set[str]] = set()

    class FakeModel:
        _meta: FakeMeta = FakeMeta()
        DoesNotExist: type[Exception] = type('DoesNotExist', (Exception,), {})
        create = staticmethod(models.Default.create)

    qs_no_obj_name: admin.Queryset = admin.Queryset(
        typing.cast(type[models.RedisValue], FakeModel)
    )
    qs_no_obj_name.slave = qs.slave
    qs_no_obj_name.master = qs.master
    with pytest.raises(
        Exception, match=r'RedisValue matching query does not exist\.'
    ):
        qs_no_obj_name.get(key='missing_key')


def test_queryset_get_keys_slice_variations(
    redis_client: redis.Redis[bytes],
) -> None:
    redis_client.set('k1', 'v1')
    redis_client.set('k2', 'v2')

    qs: admin.Queryset = admin.Queryset(models.Default, slice_limit=10)
    qs.slice = slice(None, None, None)
    keys: list[str] = qs._get_keys()
    assert 'k1' in keys
    assert 'k2' in keys


def test_queryset_fetch_metadata_skips_none(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    qs: admin.Queryset = admin.Queryset(models.Default)

    mock_pipe: mock.MagicMock = mock.MagicMock()
    mock_pipe.execute.return_value = [
        b'string',
        10000,
        5,
        b'none',
        -1,
        0,
        b'string',
        -1,
        -1,
    ]
    mock_pipe.__enter__.return_value = mock_pipe
    mock_pipe.__exit__.return_value = None

    monkeypatch.setattr(qs.slave, 'pipeline', lambda: mock_pipe)

    metadata: collections.OrderedDict[str, models.RedisValue] = (
        qs._fetch_metadata(['existing_key', 'deleted_key', 'no_ttl_key'])
    )

    assert 'existing_key' in metadata
    assert 'deleted_key' not in metadata
    assert 'no_ttl_key' in metadata

    assert metadata['existing_key'].expires_at is not None
    assert metadata['existing_key'].idle_since is not None

    assert metadata['no_ttl_key'].expires_at is None
    assert metadata['no_ttl_key'].idle_since is None


def test_queryset_fetch_values_exception_logging(
    redis_client: redis.Redis[bytes],
) -> None:
    redis_client.set('corrupt_key', 'val')

    qs: admin.Queryset = admin.Queryset(models.Default)
    values: collections.OrderedDict[str, models.RedisValue] = (
        qs._fetch_metadata(['corrupt_key'])
    )

    class BuggyValue(models.RedisString):
        class Meta(models.RedisValue.Meta):
            proxy = True
            app_label = 'redis_admin'

        @property
        def value(self) -> typing.Any:
            raise ValueError('decoding explosion')

    buggy_obj: BuggyValue = BuggyValue(key='corrupt_key', type='string')
    values['corrupt_key'] = buggy_obj

    with mock.patch('redis_admin.admin.logger.exception') as mock_log:
        qs._fetch_values(['corrupt_key'], values)
        mock_log.assert_called_once()


def test_queryset_fetch_values_response_error_fallback(
    redis_client: redis.Redis[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_client.set('fallback_key', 'val')

    qs: admin.Queryset = admin.Queryset(models.Default)
    values: collections.OrderedDict[str, models.RedisValue] = (
        qs._fetch_metadata(['fallback_key'])
    )

    original_pipeline: typing.Any = qs.slave.pipeline

    class FailingPipeline:
        def __init__(self) -> None:
            self.p: typing.Any = original_pipeline()

        def __enter__(self) -> FailingPipeline:
            return self

        def __exit__(self, *args: typing.Any) -> None:
            pass

        def __getattr__(self, name: str) -> typing.Any:
            return getattr(self.p, name)

        def execute(self) -> typing.Any:
            raise redis.ResponseError('pipeline unsupported command')

    monkeypatch.setattr(qs.slave, 'pipeline', lambda: FailingPipeline())

    qs._fetch_values(['fallback_key'], values)
    assert values['fallback_key'].raw_value == b'val'


def test_queryset_iter_cache_and_model_name_fallback(
    redis_client: redis.Redis[bytes],
) -> None:
    redis_client.set('cached_key', 'test_val')

    qs: admin.Queryset = admin.Queryset(models.Default)
    items_first: list[models.RedisValue] = list(qs)
    assert len(items_first) == 1
    assert items_first[0].key == 'cached_key'

    items_second: list[models.RedisValue] = list(qs)
    assert len(items_second) == 1
    assert items_second[0] is items_first[0]

    mock_model: mock.MagicMock = mock.MagicMock()
    mock_model._meta.model_name = None
    mock_model._meta.exclude_key_prefixes = ()
    mock_model._meta.exclude_key_re = None
    mock_model._meta.exclude_keys = ()
    mock_model.create = models.Default.create
    qs_no_model_name: admin.Queryset = admin.Queryset(
        typing.cast(type[models.RedisValue], mock_model)
    )
    qs_no_model_name.slave = qs.slave
    qs_no_model_name.master = qs.master
    items_no_name: list[models.RedisValue] = list(qs_no_model_name)
    assert len(items_no_name) == 1


def test_redis_admin_properties_and_views(
    redis_client: redis.Redis[bytes],
) -> None:
    redis_client.set('admin_test_key', 'admin_val')

    site: AdminSite = AdminSite()
    model_admin: admin.RedisAdmin = admin.RedisAdmin(models.Default, site)

    assert model_admin.show_full_result_count is False
    assert 'key' in model_admin.list_display
    assert model_admin.search_fields == ('key__contains',)
    assert len(model_admin.readonly_fields) > 0

    factory: RequestFactory = RequestFactory()
    request: typing.Any = factory.get('/admin/redis_admin/default/')
    request.user = User(
        username='superuser', is_superuser=True, is_staff=True, is_active=True
    )

    qs: admin.Queryset = model_admin.get_queryset(request)
    assert qs.slice_limit == model_admin.list_per_page + 1

    resp: typing.Any = model_admin.changelist_view(request)
    assert resp.status_code == 200

    search_request: typing.Any = factory.get(
        '/admin/redis_admin/default/?q=admin_test'
    )
    search_request.user = request.user
    search_resp: typing.Any = model_admin.changelist_view(search_request)
    assert search_resp.status_code == 200
