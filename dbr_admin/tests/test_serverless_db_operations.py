# test_serverless_db_operations.py
# Schema tests for the serverless quota tables (databricks/serverless_quota_plan.md, 2.4):
# QueryUsage, GroupQuotaState, GroupDailyUsage, IngestWatermark.
#
# SCOPE NOTE (first cut, operator decision): these tables only ever see rows
# for Spark/SQL execution (what the Query History API reports). A
# pure-Python notebook cell is invisible to this schema by design -- that
# gap is accepted for this first cut, not something these tests check for.

import pytest
from datetime import date, datetime
from peewee import SqliteDatabase, IntegrityError

from dbr_admin.database.db_operations import (
    QueryUsage, GroupQuotaState, GroupDailyUsage, IngestWatermark,
)

TEST_DB = SqliteDatabase(':memory:')
MODELS = [QueryUsage, GroupQuotaState, GroupDailyUsage, IngestWatermark]


@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    for m in MODELS:
        m.bind(TEST_DB)
    with TEST_DB.connection_context():
        TEST_DB.create_tables(MODELS)
        yield
        TEST_DB.drop_tables(MODELS)
    for m in MODELS:
        m.bind(None)


# --- QueryUsage: upsert-by-query_id is the whole point of the design (2.2) ---

def test_query_usage_running_row_has_no_duration():
    QueryUsage.create(
        query_id='q1', user_name='a@test.com', group_name='group_01',
        day=date(2026, 9, 16), start_time_ms=1_000_000, duration_ms=None,
        status='RUNNING',
    )
    row = QueryUsage.get(QueryUsage.query_id == 'q1')
    assert row.status == 'RUNNING'
    assert row.duration_ms is None
    assert row.start_time_ms == 1_000_000  # present even while running -- see plan 2.2


def test_query_usage_replace_upserts_running_to_finished():
    # This is the ingest pattern from plan 2.2: a RUNNING row polled earlier
    # is safely overwritten by its FINISHED version, never double-counted.
    QueryUsage.create(
        query_id='q1', user_name='a@test.com', group_name='group_01',
        day=date(2026, 9, 16), start_time_ms=1_000_000, duration_ms=None,
        status='RUNNING',
    )
    QueryUsage.replace(
        query_id='q1', user_name='a@test.com', group_name='group_01',
        day=date(2026, 9, 16), start_time_ms=1_000_000, duration_ms=47903.0,
        status='FINISHED',
    ).execute()

    assert QueryUsage.select().count() == 1  # still one row, not two
    row = QueryUsage.get(QueryUsage.query_id == 'q1')
    assert row.status == 'FINISHED'
    assert row.duration_ms == 47903.0


def test_query_usage_group_name_nullable_for_ungrouped():
    # Staff / service principals: reported, never blocked (plan 2.3).
    QueryUsage.create(
        query_id='q2', user_name='staff@test.com', group_name=None,
        day=date(2026, 9, 16), start_time_ms=2_000_000, duration_ms=500.0,
        status='FINISHED',
    )
    row = QueryUsage.get(QueryUsage.query_id == 'q2')
    assert row.group_name is None


def test_query_usage_filter_by_group_and_day():
    # The actual read pattern union_seconds() will use: all rows for one
    # group on one day.
    QueryUsage.create(query_id='q1', user_name='a@test.com', group_name='group_01',
                       day=date(2026, 9, 16), start_time_ms=1, duration_ms=100.0, status='FINISHED')
    QueryUsage.create(query_id='q2', user_name='b@test.com', group_name='group_01',
                       day=date(2026, 9, 16), start_time_ms=2, duration_ms=200.0, status='FINISHED')
    QueryUsage.create(query_id='q3', user_name='c@test.com', group_name='group_02',
                       day=date(2026, 9, 16), start_time_ms=3, duration_ms=300.0, status='FINISHED')
    QueryUsage.create(query_id='q4', user_name='a@test.com', group_name='group_01',
                       day=date(2026, 9, 15), start_time_ms=4, duration_ms=400.0, status='FINISHED')

    rows = list(QueryUsage.select().where(
        (QueryUsage.group_name == 'group_01') & (QueryUsage.day == date(2026, 9, 16))
    ))
    assert {r.query_id for r in rows} == {'q1', 'q2'}


# --- GroupQuotaState: one row per (group, day) ---

def test_group_quota_state_default_unblocked():
    row = GroupQuotaState.create(group_name='group_01', day=date(2026, 9, 16))
    assert row.warned is False
    assert row.blocked is False
    assert row.blocked_at is None


def test_group_quota_state_unique_per_group_and_day():
    GroupQuotaState.create(group_name='group_01', day=date(2026, 9, 16))
    with pytest.raises(IntegrityError):
        GroupQuotaState.create(group_name='group_01', day=date(2026, 9, 16))


def test_group_quota_state_same_group_different_day_allowed():
    GroupQuotaState.create(group_name='group_01', day=date(2026, 9, 16))
    GroupQuotaState.create(group_name='group_01', day=date(2026, 9, 17))  # should not raise
    assert GroupQuotaState.select().where(GroupQuotaState.group_name == 'group_01').count() == 2


def test_group_quota_state_block_transition():
    row = GroupQuotaState.create(group_name='group_01', day=date(2026, 9, 16))
    row.blocked = True
    row.blocked_at = datetime(2026, 9, 16, 10, 52, 56)
    row.save()

    reloaded = GroupQuotaState.get(
        (GroupQuotaState.group_name == 'group_01') & (GroupQuotaState.day == date(2026, 9, 16))
    )
    assert reloaded.blocked is True
    assert reloaded.blocked_at == datetime(2026, 9, 16, 10, 52, 56)


# --- GroupDailyUsage: historical rollup, one row per (group, date) ---

def test_group_daily_usage_unique_per_group_and_date():
    GroupDailyUsage.create(group_name='group_01', date=date(2026, 9, 16), used_seconds=960.0)
    with pytest.raises(IntegrityError):
        GroupDailyUsage.create(group_name='group_01', date=date(2026, 9, 16), used_seconds=1.0)


def test_group_daily_usage_defaults_to_zero():
    row = GroupDailyUsage.create(group_name='group_01', date=date(2026, 9, 16))
    assert row.used_seconds == 0.0


# --- IngestWatermark: one row per backend, advances forward ---

def test_ingest_watermark_get_or_create_defaults_to_zero():
    row, created = IngestWatermark.get_or_create(
        backend='serverless_query_history', defaults={'last_seen_ms': 0}
    )
    assert created is True
    assert row.last_seen_ms == 0


def test_ingest_watermark_advances():
    row, _ = IngestWatermark.get_or_create(
        backend='serverless_query_history', defaults={'last_seen_ms': 0}
    )
    row.last_seen_ms = 1_789_544_737_861
    row.save()

    reloaded = IngestWatermark.get(IngestWatermark.backend == 'serverless_query_history')
    assert reloaded.last_seen_ms == 1_789_544_737_861


def test_ingest_watermark_one_row_per_backend():
    IngestWatermark.create(backend='serverless_query_history', last_seen_ms=100)
    with pytest.raises(IntegrityError):
        IngestWatermark.create(backend='serverless_query_history', last_seen_ms=200)
