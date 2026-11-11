# test_error_report.py -- "all errors must be reported": throttled admin emails, recovery, health.

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase

from dbr_admin.database.db_operations import ErrorReport, JobRunCount
from dbr_admin.resource_manager import error_report as er
from dbr_admin import job_status

TEST_DB = SqliteDatabase(':memory:')
T0 = datetime(2026, 11, 11, 10, 0)


@pytest.fixture(autouse=True)
def db():
    ErrorReport.bind(TEST_DB)
    JobRunCount.bind(TEST_DB)
    with TEST_DB.connection_context():
        TEST_DB.create_tables([ErrorReport, JobRunCount])
        yield
        TEST_DB.drop_tables([ErrorReport, JobRunCount])
    ErrorReport.bind(None)
    JobRunCount.bind(None)


def test_first_error_emails_then_throttles_then_reminds():
    send = MagicMock()
    assert er.report_error('periodic_poll', 'exit status', 'boom', send, 'admin@x', now=T0)
    subject, body, to, _ = send.call_args.args
    assert subject == 'ERROR: periodic_poll: exit status' and to == ['admin@x'] and 'boom' in body

    send.reset_mock()
    for m in (15, 30, 45):
        assert not er.report_error('periodic_poll', 'exit status', 'boom', send, 'admin@x',
                                   now=T0 + timedelta(minutes=m))
    send.assert_not_called()

    assert er.report_error('periodic_poll', 'exit status', 'boom', send, 'admin@x',
                           now=T0 + timedelta(hours=er.REPEAT_HOURS))
    assert 'still failing' in send.call_args.args[0] and '5 times' in send.call_args.args[1]


def test_recovery_emails_once_and_clears():
    send = MagicMock()
    er.report_error('gpu_alert', 'check skipped', 'x', send, 'a', now=T0)
    send.reset_mock()
    assert er.report_ok('gpu_alert', 'check skipped', send, 'a') == 1
    assert send.call_args.args[0] == 'RECOVERED: gpu_alert: check skipped'
    assert er.report_ok('gpu_alert', 'check skipped', send, 'a') == 0   # nothing open -> no email
    assert send.call_count == 1


def test_failed_send_is_retried_next_time_and_never_raises():
    bad = MagicMock(side_effect=RuntimeError('smtp down'))
    assert not er.report_error('j', 'k', 'x', bad, 'a', now=T0)
    good = MagicMock()
    assert er.report_error('j', 'k', 'x', good, 'a', now=T0 + timedelta(minutes=15))


def test_report_never_raises_without_db():
    ErrorReport.bind(None)
    try:
        assert er.report_error('j', 'k', 'x', MagicMock(), 'a') is False
        assert er.report_ok('j', 'k', MagicMock(), 'a') == 0
    finally:
        ErrorReport.bind(TEST_DB)


def test_job_status_timeout_is_reported_with_journal_tail():
    send = MagicMock()
    job_status.handle('periodic_poll', 124, send_emails=send, tail=lambda: 'Periodic Poll starting')
    subject, body, _, _ = send.call_args.args
    assert 'periodic_poll' in subject
    assert 'exit code 124 (killed by timeout)' in body and 'Periodic Poll starting' in body

    send.reset_mock()
    job_status.handle('periodic_poll', 0, send_emails=send)
    assert send.call_args.args[0].startswith('RECOVERED')
    r = JobRunCount.get(JobRunCount.job == 'periodic_poll')
    assert (r.ok, r.failed) == (1, 1)


def test_job_status_success_without_open_error_sends_nothing():
    send = MagicMock()
    job_status.handle('gpu_alert', 0, send_emails=send)
    send.assert_not_called()


def test_health_report_flags_failures_missing_runs_and_open_errors():
    d = date(2026, 11, 10)
    for _ in range(96):
        er.record_run('periodic_poll', True, day=d)
    er.record_run('gpu_alert', True, day=d)          # 1 of 4 -> missing runs
    er.record_run('billing_backstop', False, day=d)  # a failure
    er.report_error('billing_backstop', 'query failed', 'x', MagicMock(), 'a', now=T0)
    html = er.health_report_html(d)
    row = lambda job: next(l.split('</tr>')[0] for l in html.split('<tr') if f'>{job}<' in l)
    poll_row = row('periodic_poll')
    gpu_row = row('gpu_alert')
    eod_row = row('end_of_day')
    assert 'color:red' not in poll_row
    assert 'color:red' in gpu_row and 'color:red' in eod_row     # eod never ran
    assert 'Open errors' in html and 'billing_backstop: query failed' in html


def test_backstop_query_failure_is_reported_and_recovery_closes_it(monkeypatch):
    from dbr_admin.resource_manager import serverless_billing as sb
    sent = MagicMock()
    monkeypatch.setattr(er, '_default_send', lambda: sent)
    monkeypatch.setattr(sb, 'fetch_billed_seconds_per_user',
                        MagicMock(side_effect=RuntimeError('no access to system.billing.usage')))
    assert sb.backstop_check(MagicMock(), 'wh', {}, 300 * 60) == set()
    assert sent.call_args.args[0] == 'ERROR: billing_backstop: query failed'
    assert 'no access' in sent.call_args.args[1]

    monkeypatch.setattr(sb, 'fetch_billed_seconds_per_user', MagicMock(return_value={'u@x': 99999.0}))
    assert sb.backstop_check(MagicMock(), 'wh', {'u@x': 'group_01'}, 300 * 60) == {'group_01'}
    assert sent.call_args.args[0] == 'RECOVERED: billing_backstop: query failed'
    r = JobRunCount.get(JobRunCount.job == 'billing_backstop')
    assert (r.ok, r.failed) == (1, 1)
