"""
Called by every cron wrapper after its job, with the job's exit code:

    timeout -k 10 90 python -m dbr_admin.poll_clusters; rc=$?
    python -m dbr_admin.job_status periodic_poll $rc

rc 0 counts a good run and closes an open error (one "recovered" email).
Any other rc counts a failed run and emails ADMIN_EMAIL (throttled, see
resource_manager/error_report.py), with the last journal lines attached.
This is what reports timeout kills and config errors, which the jobs themselves can't.
"""
import logging
import subprocess
import sys

KINDS = {124: 'killed by timeout', 137: 'killed by timeout (SIGKILL)'}


def journal_tail(lines: int = 40) -> str:
    try:
        return subprocess.run(['journalctl', '-t', 'dbr_scripts', '--since', '-15 min', '-n', str(lines),
                               '--no-pager', '-o', 'short-iso'],
                              capture_output=True, text=True, timeout=20).stdout
    except Exception as ex:
        return f"(could not read journal: {ex})"


def handle(job: str, rc: int, send_emails=None, tail=journal_tail) -> None:
    from .resource_manager.error_report import record_run, report_error, report_ok
    record_run(job, rc == 0)
    if rc == 0:
        report_ok(job, 'exit status', send_emails=send_emails)
        return
    kind = 'exit status'
    detail = f"exit code {rc} ({KINDS.get(rc, 'non-zero exit')})\n\nlast journal lines:\n{tail()}"
    report_error(job, kind, detail, send_emails=send_emails)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    from .database.db_operations import create_tables, initialize_production_db
    prod_db = initialize_production_db()
    with prod_db.connection_context():
        create_tables(prod_db)
        handle(sys.argv[1], int(sys.argv[2]))
