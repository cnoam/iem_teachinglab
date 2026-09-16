"""
Classic backend: dedicated per-group clusters (../terraform/dbr/).

This wraps today's cluster-uptime-monitor code unchanged -- every method here
is a one-line delegation to the existing function in poll_clusters.py,
restore_cluster_permissions.py, end_of_day_operations.py or
resource_manager/cluster_uptime.py. Nothing is reimplemented, so this backend
has zero behavior change from before this refactor.

Imported here at module level using the canonical absolute dotted path
(databricks.poll_clusters, not a relative "self" import), and this module is
never itself run as a script -- so instantiating ClassicBackend from outside
poll_clusters.py / end_of_day_operations.py (e.g. from a future shared
script, or from tests) is safe. The two cron entry points' own
`__main__` blocks call their local functions directly for the classic case
rather than going through this class, specifically to avoid the well-known
`python -m package.module` double-import gotcha (the module would otherwise
get imported once as `__main__` and once under its canonical dotted name).

IMPORTANT: because of the above, this class is NOT on the production classic
path today -- nothing in poll_clusters.py or end_of_day_operations.py's
`__main__` blocks constructs a ClassicBackend; only this module's own tests
do. It exists so Step 2's serverless path (and any future shared caller) has
a stable, symmetric interface to program against, and so the wrapping is
provably correct by test even though it's not exercised in production.
Editing a method here has NO effect on the real classic cron jobs -- edit
the wrapped function itself for that. Also note report() only generates
HTML; it does not email it (unlike end_of_day_operations.send_usage_report(),
which does both) -- there is deliberately no send-and-email method on this
interface yet, so Step 2 will need one before the serverless daily report can
actually be emailed.
"""
from .base import UsageBackend
from ...poll_clusters import main as _poll_clusters_main
from ...restore_cluster_permissions import restore_cluster_permissions as _restore_cluster_permissions
from ...end_of_day_operations import log_daily_uptime as _log_daily_uptime
from ..cluster_uptime import create_usage_report_daily as _create_usage_report_daily


class ClassicBackend(UsageBackend):
    """Wraps the existing dedicated-cluster quota monitor. No behavior change."""

    def collect_and_enforce(self):
        _poll_clusters_main()

    def restore(self, host, token, logger):
        _restore_cluster_permissions(host, token, logger)

    def roll_up_and_reset(self, prod_db, logger):
        _log_daily_uptime(prod_db, logger)

    def report(self, when) -> str:
        return _create_usage_report_daily(when)
