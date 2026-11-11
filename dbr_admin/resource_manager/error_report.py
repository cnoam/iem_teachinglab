"""
Every error must reach the admin by email (operator rule, 2026-11-11).

- report_error(job, kind, detail): email ADMIN_EMAIL at once on a new error; while the same
  (job, kind) keeps failing, at most one "still failing" email per REPEAT_HOURS (a broken
  15-min poll would otherwise send 96 emails/day).
- report_ok(job, kind): if that error was open, send one "recovered" email and close it.
- record_run(job, ok): per-day run counts, shown in the daily report's health section,
  which also exposes runs that never happened (cron stopped, server down).

None of these ever raise: they are called from non-fatal paths (billing backstop, warehouse
stop). A failure to report is logged; the daily health section is the fallback, and a
missing daily report is itself the alarm.
"""
import logging
import os
from datetime import date, datetime, timedelta
from html import escape

from ..database.db_operations import ErrorReport, JobRunCount

REPEAT_HOURS = 6

# Runs per day when everything works -- must match the server crontab (README.md).
EXPECTED_RUNS_PER_DAY = {
    'periodic_poll': 96,      # */15
    'billing_backstop': 24,   # inside the poll, SERVERLESS_BACKSTOP_INTERVAL_MINUTES=60
    'gpu_alert': 4,           # 23 7,12,17,22
    'end_of_day': 1,          # 7 0
}


def _default_send():
    from .user_mail import send_emails
    return send_emails


def report_error(job: str, kind: str, detail: str, send_emails=None, admin_email: str = None,
                 logger: logging.Logger = None, now: datetime = None) -> bool:
    """Record the error; email if new or REPEAT_HOURS since the last email. Returns True if emailed."""
    logger = logger or logging.getLogger('ERROR_REPORT')
    now = now or datetime.now()
    try:
        key = f"{job}|{kind}"
        row, created = ErrorReport.get_or_create(
            key=key, defaults={'job': job, 'kind': kind, 'first_at': now, 'last_at': now})
        row.count += 1
        row.last_at = now
        row.last_detail = detail[-4000:]
        row.save()
        due = row.last_emailed_at is None or now - row.last_emailed_at >= timedelta(hours=REPEAT_HOURS)
        if not due:
            logger.warning(f"{job}: {kind} again ({row.count}x since {row.first_at:%Y-%m-%d %H:%M}); "
                           f"email throttled")
            return False
        if row.count == 1:
            subject = f"ERROR: {job}: {kind}"
            intro = "A scheduled check failed."
        else:
            subject = f"ERROR (still failing): {job}: {kind}"
            intro = (f"Still failing: {row.count} times since {row.first_at:%Y-%m-%d %H:%M}. "
                     f"Next reminder in {REPEAT_HOURS}h if it keeps failing.")
        body = (f"<p>{escape(intro)}</p><p>job: <b>{escape(job)}</b>, error: <b>{escape(kind)}</b>, "
                f"at {now:%Y-%m-%d %H:%M:%S}</p><pre>{escape(detail[-4000:])}</pre>")
        (send_emails or _default_send())(subject, body, [admin_email or os.getenv('ADMIN_EMAIL')], logger)
        row.last_emailed_at = now
        row.save()
        return True
    except Exception as ex:
        logger.error(f"could not report error {job}/{kind}: {ex}")
        return False


def report_ok(job: str, kind: str = None, send_emails=None, admin_email: str = None,
              logger: logging.Logger = None, now: datetime = None) -> int:
    """Close open errors of `job` (one kind, or all if kind is None); one 'recovered' email each."""
    logger = logger or logging.getLogger('ERROR_REPORT')
    now = now or datetime.now()
    closed = 0
    try:
        q = ErrorReport.select().where(ErrorReport.job == job)
        if kind is not None:
            q = q.where(ErrorReport.kind == kind)
        for row in list(q):
            (send_emails or _default_send())(
                f"RECOVERED: {job}: {row.kind}",
                f"<p><b>{escape(job)}</b> is working again at {now:%Y-%m-%d %H:%M}. "
                f"Error <b>{escape(row.kind)}</b> happened {row.count} time(s) since "
                f"{row.first_at:%Y-%m-%d %H:%M}.</p>",
                [admin_email or os.getenv('ADMIN_EMAIL')], logger)
            row.delete_instance()
            closed += 1
    except Exception as ex:
        logger.error(f"could not close errors for {job}: {ex}")
    return closed


def record_run(job: str, ok: bool, day: date = None, logger: logging.Logger = None) -> None:
    try:
        day = day or date.today()
        JobRunCount.insert(day=day, job=job, ok=0, failed=0).on_conflict_ignore().execute()
        field = JobRunCount.ok if ok else JobRunCount.failed
        (JobRunCount.update({field: field + 1})
         .where((JobRunCount.day == day) & (JobRunCount.job == job)).execute())
    except Exception as ex:
        (logger or logging.getLogger('ERROR_REPORT')).error(f"could not record run of {job}: {ex}")


def health_report_html(day: date) -> str:
    """Run counts for `day` vs expected, plus all open errors. Problems are marked in red."""
    counts = {r.job: r for r in JobRunCount.select().where(JobRunCount.day == day)}
    rows = []
    for job in sorted(set(EXPECTED_RUNS_PER_DAY) | set(counts)):
        r = counts.get(job)
        ok, failed = (r.ok, r.failed) if r else (0, 0)
        expected = EXPECTED_RUNS_PER_DAY.get(job)
        bad = failed > 0 or (expected is not None and ok + failed < expected)
        style = " style='color:red;font-weight:bold'" if bad else ""
        rows.append(f"<tr{style}><td>{escape(job)}</td><td>{expected if expected is not None else '-'}</td>"
                    f"<td>{ok}</td><td>{failed}</td></tr>")
    open_errors = list(ErrorReport.select().order_by(ErrorReport.first_at))
    errs = "".join(
        f"<li><b>{escape(e.job)}: {escape(e.kind)}</b> -- {e.count}x since {e.first_at:%Y-%m-%d %H:%M}, "
        f"last {e.last_at:%Y-%m-%d %H:%M}</li>" for e in open_errors)
    return (f"<h3>Health of scheduled checks, {day.isoformat()}</h3>"
            "<p>If this daily report stops arriving, the server or its email itself is broken.</p>"
            "<table border='1' cellpadding='4'><tr><th>job</th><th>expected runs</th><th>ok</th>"
            "<th>failed</th></tr>" + "".join(rows) + "</table>"
            + (f"<p style='color:red'><b>Open errors:</b></p><ul>{errs}</ul>" if open_errors
               else "<p>No open errors.</p>"))


def purge_run_counts(keep_days: int = 35) -> None:
    JobRunCount.delete().where(JobRunCount.day < date.today() - timedelta(days=keep_days)).execute()

