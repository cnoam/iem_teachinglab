# test_serverless_backend.py
# Step 2 of databricks/serverless_quota_plan.md: ServerlessBackend's real
# implementation. All external calls (DataBricksGroups, the SCIM
# block/restore lever, email) are mocked; the DB layer (GroupQuotaState,
# GroupDailyUsage, QueryUsage) is real, bound to an in-memory sqlite DB, so
# the actual read/write logic gets exercised.

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from peewee import SqliteDatabase

from dbr_admin.resource_manager.backends.serverless import ServerlessBackend
from dbr_admin.database.db_operations import GroupQuotaState, GroupDailyUsage, QueryUsage, IngestWatermark

TEST_DB = SqliteDatabase(':memory:')
MODELS = [GroupQuotaState, GroupDailyUsage, QueryUsage, IngestWatermark]

MOD = 'dbr_admin.resource_manager.backends.serverless'


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


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('DATABRICKS_HOST', 'example.databricks.net')
    monkeypatch.setenv('DATABRICKS_TOKEN', 'test-token')
    monkeypatch.setenv('SERVERLESS_WARN_EXEC_MINUTES', '10')  # 600s
    monkeypatch.setenv('SERVERLESS_MAX_EXEC_MINUTES', '15')   # 900s
    monkeypatch.delenv('SERVERLESS_BILLING_WAREHOUSE_ID', raising=False)


# --- collect_and_enforce(): threshold decisions ---

@patch(f'{MOD}.backstop_check', return_value=set())
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_blocks_group_over_max_quota(MockGroups, _map, _ingest, mock_usage,
                                      mock_block, mock_send, _backstop):
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 1000.0  # > 900s max
    mock_block.return_value = True

    ServerlessBackend().collect_and_enforce()

    mock_block.assert_called_once()
    assert mock_block.call_args.args[1] == 'group_01'  # block_group(client, group_name, logger)
    mock_send.assert_called_once()
    assert 'quota' in mock_send.call_args.kwargs['subject'].lower()

    state = GroupQuotaState.get(
        (GroupQuotaState.group_name == 'group_01') & (GroupQuotaState.day == date.today())
    )
    assert state.blocked is True
    assert state.warned is False  # never crossed warn separately -- went straight past both


@patch(f'{MOD}.backstop_check', return_value=set())
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_warns_but_does_not_block_between_thresholds(MockGroups, _map, _ingest, mock_usage,
                                                       mock_block, mock_send, _backstop):
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 700.0  # between warn (600s) and max (900s)

    ServerlessBackend().collect_and_enforce()

    mock_block.assert_not_called()
    mock_send.assert_called_once()
    assert 'approaching' in mock_send.call_args.kwargs['subject'].lower()

    state = GroupQuotaState.get(
        (GroupQuotaState.group_name == 'group_01') & (GroupQuotaState.day == date.today())
    )
    assert state.warned is True
    assert state.blocked is False


# --- billing backstop (plan 2.6a): catches what the primary quota can't ---

@patch(f'{MOD}.backstop_check')
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_backstop_blocks_group_the_primary_check_missed(MockGroups, _map, _ingest, mock_usage,
                                                          mock_block, mock_send, mock_backstop):
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 0.0  # primary check sees nothing -- this is the whole point of 1a/2.6a
    mock_backstop.return_value = {'group_01'}
    mock_block.return_value = True

    ServerlessBackend().collect_and_enforce()

    assert mock_block.called
    mock_send.assert_called_once()
    assert 'backstop' in mock_send.call_args.kwargs['subject'].lower()

    state = GroupQuotaState.get(
        (GroupQuotaState.group_name == 'group_01') & (GroupQuotaState.day == date.today())
    )
    assert state.blocked is True


@patch(f'{MOD}.backstop_check')
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_backstop_reasserts_but_never_reemails_for_already_blocked_group(
        MockGroups, _map, _ingest, mock_usage, mock_block, mock_send, mock_backstop):
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 1000.0  # primary check blocks it first
    mock_backstop.return_value = {'group_01'}  # backstop also flags the same group
    mock_block.return_value = True

    ServerlessBackend().collect_and_enforce()

    # Primary check blocks + emails once; backstop sees it already blocked
    # and only re-asserts (no second email).
    assert mock_block.call_count == 2
    mock_send.assert_called_once()


@patch(f'{MOD}.backstop_check', return_value=set())
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_second_poll_reasserts_block_but_never_reemails(MockGroups, _map, _ingest, mock_usage,
                                                          mock_block, mock_send, _backstop):
    # Re-asserting the block every poll is deliberate (plan 2.5: self-heals
    # against a mid-day terraform apply that silently restores the group).
    # The student should never be re-notified for the same day, though.
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 1000.0
    mock_block.return_value = True

    backend = ServerlessBackend()
    backend.collect_and_enforce()
    backend.collect_and_enforce()  # simulates the next poll cycle, still over quota

    assert mock_block.call_count == 2  # re-asserted, not skipped
    mock_send.assert_called_once()     # but never re-notified

    state = GroupQuotaState.get(
        (GroupQuotaState.group_name == 'group_01') & (GroupQuotaState.day == date.today())
    )
    assert state.blocked is True
    assert state.warned is False  # confirms the bug this test caught: never
    # falls through to the warn branch once already blocked


@patch(f'{MOD}.backstop_check', return_value=set())
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_backstop_skipped_on_rapid_second_poll(MockGroups, _map, _ingest, mock_usage,
                                                mock_block, mock_send, mock_backstop):
    # Decoupled cadence (operator request 2026-09-16): the backstop should
    # not run on every 15-min poll cycle, only once per
    # SERVERLESS_BACKSTOP_INTERVAL_MINUTES. The primary quota check (mocked
    # here to do nothing) is unaffected either way.
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 0.0  # primary check: well under quota, does nothing

    backend = ServerlessBackend()
    backend.collect_and_enforce()
    backend.collect_and_enforce()  # immediately-following poll cycle

    assert mock_backstop.call_count == 1  # not re-run on the second, rapid poll


@patch(f'{MOD}.backstop_check', return_value=set())
@patch(f'{MOD}.send_emails')
@patch(f'{MOD}.block_group')
@patch(f'{MOD}.group_usage_seconds_for_day')
@patch(f'{MOD}.ingest_collect')
@patch(f'{MOD}.build_email_to_group_map', return_value={'a@test.com': 'group_01'})
@patch(f'{MOD}.DataBricksGroups')
def test_under_warn_threshold_does_nothing(MockGroups, _map, _ingest, mock_usage,
                                            mock_block, mock_send, _backstop):
    MockGroups.return_value.get_group_members.return_value = [{'user_name': 'a@test.com'}]
    mock_usage.return_value = 100.0  # well under warn

    ServerlessBackend().collect_and_enforce()

    mock_block.assert_not_called()
    mock_send.assert_not_called()


# --- restore(): only group_NN-pattern groups get restored ---

@patch(f'{MOD}.restore_group')
@patch(f'{MOD}.DataBricksGroups')
def test_restore_only_matches_group_name_pattern(MockGroups, mock_restore):
    MockGroups.return_value.list_groups.return_value = [
        'group_01', 'group_02', 'all_student_groups', 'admins',
    ]
    ServerlessBackend().restore('host', 'token', MagicMock())

    restored = {call.args[1] for call in mock_restore.call_args_list}  # restore_group(client, group_name, logger)
    assert restored == {'group_01', 'group_02'}


# --- roll_up_and_reset(): real DB integration (union_seconds computed for real) ---

def test_roll_up_and_reset_aggregates_yesterday_and_purges_old_rows():
    yesterday = date.today() - timedelta(days=1)
    old_day = date.today() - timedelta(days=40)  # older than RETENTION_DAYS (35)

    QueryUsage.create(query_id='q1', user_name='a@test.com', group_name='group_01',
                       day=yesterday, start_time_ms=0, duration_ms=120_000, status='FINISHED')
    QueryUsage.create(query_id='q2', user_name='b@test.com', group_name='group_01',
                       day=yesterday, start_time_ms=200_000, duration_ms=60_000, status='FINISHED')
    QueryUsage.create(query_id='q3', user_name='c@test.com', group_name='group_02',
                       day=yesterday, start_time_ms=0, duration_ms=30_000, status='FINISHED')
    QueryUsage.create(query_id='q_old', user_name='a@test.com', group_name='group_01',
                       day=old_day, start_time_ms=0, duration_ms=5_000, status='FINISHED')

    ServerlessBackend().roll_up_and_reset(prod_db=TEST_DB, logger=MagicMock())

    g1 = GroupDailyUsage.get((GroupDailyUsage.group_name == 'group_01') & (GroupDailyUsage.date == yesterday))
    assert g1.used_seconds == 180.0  # 120s + 60s, non-overlapping -> union == sum
    g2 = GroupDailyUsage.get((GroupDailyUsage.group_name == 'group_02') & (GroupDailyUsage.date == yesterday))
    assert g2.used_seconds == 30.0

    # old row purged, yesterday's rows untouched
    assert QueryUsage.select().where(QueryUsage.query_id == 'q_old').count() == 0
    assert QueryUsage.select().where(QueryUsage.day == yesterday).count() == 3


# --- report(): HTML rendering ---

def test_report_renders_rows_and_total():
    when = date(2026, 9, 16)
    GroupDailyUsage.create(group_name='group_01', date=when, used_seconds=3600)  # 1:00
    GroupDailyUsage.create(group_name='group_02', date=when, used_seconds=1800)  # 0:30

    html = ServerlessBackend().report(when)

    assert 'group_01' in html and 'group_02' in html
    assert '01:00' in html
    assert '00:30' in html
    assert '01:30' in html  # total


def test_report_handles_no_rows():
    html = ServerlessBackend().report(date(2026, 9, 16))
    assert 'No usage recorded' in html
