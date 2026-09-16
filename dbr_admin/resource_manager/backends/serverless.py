"""
Serverless backend: Step 2 of databricks/serverless_quota_plan.md.

SCOPE NOTE, first cut (operator decision): this backend only detects and
enforces on Spark/SQL execution visible through the Query History API. A
pure-Python notebook cell is invisible to the primary quota (plan 1a) --
accepted limitation, not a bug; that is considered PASS for this cut. The
system.billing.usage backstop (serverless_billing.py, plan 2.6a) is the
only, hours-delayed, mechanism that eventually catches that gap.

Enforcement (block_group / restore_group, plan 2.5) blocks *new* command
dispatch and page access -- confirmed live -- but does not, and per the
current state of things cannot, terminate a command already running.
"""
import logging
import os
from datetime import date, datetime, timedelta

from databricks.sdk import WorkspaceClient

from .base import UsageBackend
from ...DataBricksGroups import DataBricksGroups
from ..dbr_host import normalize_dbr_host
from ..group_map import build_email_to_group_map, GROUP_NAME_PATTERN
from ..serverless_usage import collect as ingest_collect, group_usage_seconds_for_day
from ..serverless_enforcement import block_group, restore_group
from ..serverless_billing import backstop_check, should_run_backstop
from ..user_mail import send_emails
from ..cluster_uptime import format_timedelta_to_hhmm
from ...database.db_operations import GroupQuotaState, GroupDailyUsage, QueryUsage

# Provisional defaults (plan 2.7) -- not derived from real usage data,
# recalibrate once real data exists.
DEFAULT_WARN_MINUTES = 120
DEFAULT_MAX_MINUTES = 150
DEFAULT_BACKSTOP_MINUTES = 300

# The backstop runs on its own, slower cadence than the primary poll cycle
# (operator request 2026-09-16: was previously running every single
# collect_and_enforce() call, i.e. every 15 min via cron -- cold-starting
# the billing warehouse each time). See should_run_backstop() in
# serverless_billing.py.
DEFAULT_BACKSTOP_INTERVAL_MINUTES = 60

# How long QueryUsage rows are kept before roll_up_and_reset() purges them
# (plan 2.6: "purge QueryUsage rows older than the retention window").
RETENTION_DAYS = 35


class ServerlessBackend(UsageBackend):

    def collect_and_enforce(self):
        logger = logging.getLogger('SERVERLESS_BACKEND')
        host = normalize_dbr_host(os.getenv('DATABRICKS_HOST'))
        token = os.getenv('DATABRICKS_TOKEN')
        warn_seconds = float(os.getenv('SERVERLESS_WARN_EXEC_MINUTES', DEFAULT_WARN_MINUTES)) * 60
        max_seconds = float(os.getenv('SERVERLESS_MAX_EXEC_MINUTES', DEFAULT_MAX_MINUTES)) * 60
        backstop_seconds = float(os.getenv('SERVERLESS_BACKSTOP_MINUTES', DEFAULT_BACKSTOP_MINUTES)) * 60
        backstop_interval_seconds = float(
            os.getenv('SERVERLESS_BACKSTOP_INTERVAL_MINUTES', DEFAULT_BACKSTOP_INTERVAL_MINUTES)
        ) * 60
        billing_warehouse_id = os.getenv('SERVERLESS_BILLING_WAREHOUSE_ID')

        # One SDK client, reused for every call this cycle (query history,
        # SCIM block/restore, the billing backstop). group_map.py still
        # goes through DataBricksGroups -- a deliberate reuse (see its
        # docstring), not a naming-collision workaround.
        client = WorkspaceClient(host=host, token=token)
        groups_api = DataBricksGroups(host=host, token=token)
        email_to_group = build_email_to_group_map(groups_api, logger)

        ingest_collect(client, email_to_group, logger)

        today = date.today()
        for group_name in sorted(set(email_to_group.values())):
            self._check_and_enforce_group(
                group_name, today, client, groups_api,
                warn_seconds, max_seconds, logger,
            )

        # Backstop (plan 2.6a): catches what the primary quota structurally
        # cannot -- pure-Python compute (1a). Best-effort, never raises. On
        # its own, slower cadence than this poll -- see
        # SERVERLESS_BACKSTOP_INTERVAL_MINUTES; most cycles skip it here.
        if not should_run_backstop(backstop_interval_seconds):
            return
        for group_name in backstop_check(client, billing_warehouse_id,
                                          email_to_group, backstop_seconds, logger):
            state, _ = GroupQuotaState.get_or_create(group_name=group_name, day=today)
            if state.blocked:
                # Same re-assert-but-never-re-notify rule as the primary
                # check (this may well be the group the primary check just
                # blocked, or a repeat backstop trip -- either way, no
                # second email for the same day).
                block_group(client, group_name, logger)
                continue
            state.blocked = True
            state.blocked_at = datetime.now()
            state.save()
            if block_group(client, group_name, logger):
                self._notify_group(
                    groups_api, group_name,
                    subject=f"'{group_name}' blocked (billing backstop)",
                    body=(
                        "Your group's actual billed compute time today exceeded a safety "
                        "threshold, even though it looked within quota by our normal check. "
                        "This usually means code left running unattended. You are blocked "
                        "from starting new work until the quota resets at midnight. Work "
                        "already running is not affected."
                    ),
                    logger=logger,
                )

    def _check_and_enforce_group(self, group_name, today, client, groups_api,
                                  warn_seconds, max_seconds, logger):
        usage_seconds = group_usage_seconds_for_day(group_name, today)
        state, _ = GroupQuotaState.get_or_create(group_name=group_name, day=today)

        if state.blocked:
            # Already handled today -- re-asserted on every poll per plan
            # 2.5 (self-healing against a mid-day terraform apply lifting
            # the block), but never re-notified and never falls through to
            # the warn branch below.
            block_group(client, group_name, logger)
            return

        if usage_seconds >= max_seconds:
            state.blocked = True
            state.blocked_at = datetime.now()
            state.save()
            if block_group(client, group_name, logger):
                self._notify_group(
                    groups_api, group_name,
                    subject=f"'{group_name}' has used its daily compute quota",
                    body=(
                        f"Your group has used {usage_seconds / 60:.0f} minutes of compute today "
                        f"(quota: {max_seconds / 60:.0f} minutes). You are blocked from starting "
                        f"new work until the quota resets at midnight. Work already running is "
                        f"not affected -- this blocks new commands and logins, not what's "
                        f"currently executing."
                    ),
                    logger=logger,
                )
        elif usage_seconds >= warn_seconds and not state.warned:
            state.warned = True
            state.save()
            self._notify_group(
                groups_api, group_name,
                subject=f"'{group_name}' is approaching its daily compute quota",
                body=(
                    f"Your group has used {usage_seconds / 60:.0f} minutes of compute today "
                    f"out of a {max_seconds / 60:.0f} minute daily quota."
                ),
                logger=logger,
            )

    @staticmethod
    def _notify_group(groups_api, group_name, subject, body, logger):
        try:
            recipients = [m['user_name'] for m in groups_api.get_group_members(group_name)]
        except Exception as ex:
            logger.error(f"Could not resolve members of {group_name} to notify: {ex}")
            recipients = []
        if recipients:
            send_emails(subject=subject, body=body, recipients=recipients, logger=logger)

    def restore(self, host, token, logger):
        # end_of_day_operations.py passes the raw DATABRICKS_HOST env var
        # (no scheme) -- normalize here rather than trust the caller.
        # DataBricksGroups still requires an explicit scheme; WorkspaceClient
        # would normalize it itself, but there's no harm doing it once up
        # front for both.
        host = normalize_dbr_host(host)
        client = WorkspaceClient(host=host, token=token)
        groups_api = DataBricksGroups(host=host, token=token)
        for group_name in groups_api.list_groups():
            if GROUP_NAME_PATTERN.match(group_name):
                restore_group(client, group_name, logger)

    def roll_up_and_reset(self, prod_db, logger):
        yesterday = date.today() - timedelta(days=1)
        cutoff = date.today() - timedelta(days=RETENTION_DAYS)

        with prod_db.atomic():
            groups = {
                row.group_name for row in QueryUsage
                .select(QueryUsage.group_name)
                .where((QueryUsage.day == yesterday) & (QueryUsage.group_name.is_null(False)))
                .distinct()
            }
            for group_name in groups:
                used = group_usage_seconds_for_day(group_name, yesterday)
                GroupDailyUsage.replace(group_name=group_name, date=yesterday, used_seconds=used).execute()

            deleted = QueryUsage.delete().where(QueryUsage.day < cutoff).execute()

        logger.info(
            f"Serverless roll-up for {yesterday}: {len(groups)} groups, "
            f"purged {deleted} QueryUsage rows older than {cutoff}."
        )

    def report(self, when) -> str:
        rows = list(GroupDailyUsage.select().where(GroupDailyUsage.date == when))
        lines = [f"<h1>Daily Serverless Usage Report - {when}</h1>"]
        if not rows:
            lines.append(f"<p>No usage recorded for {when}.</p>")
            return "\n".join(lines)

        lines.append('<table border="1" style="border-collapse: collapse; width: 50%;">')
        lines.append(
            '<tr><th style="text-align:left;">Group</th>'
            '<th style="text-align:right;">Usage (HH:MM)</th></tr>'
        )
        total_seconds = 0.0
        for row in rows:
            total_seconds += row.used_seconds
            lines.append(
                f'<tr><td style="text-align:left;">{row.group_name}</td>'
                f'<td style="text-align:right;">'
                f'{format_timedelta_to_hhmm(timedelta(seconds=row.used_seconds))}</td></tr>'
            )
        lines.append('</table>')
        lines.append(
            f"<h2>Total Daily Recorded Usage: "
            f"{format_timedelta_to_hhmm(timedelta(seconds=total_seconds))}</h2>"
        )
        return "\n".join(lines)
