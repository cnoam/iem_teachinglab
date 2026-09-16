"""
Abstract interface for a usage-quota backend (classic dedicated clusters vs.
serverless compute).

Step 1 of databricks/serverless_quota_plan.md: introduce this interface with
a ClassicBackend that wraps today's cluster-uptime-monitor code unchanged,
and a ServerlessBackend stub that Step 2 of the plan will implement. QUOTA_MODE
(env var, default 'classic') selects which backend the two cron entry points
(poll_clusters.py, end_of_day_operations.py) use.

See databricks/serverless_quota_plan.md for the full design and rationale.
"""
from abc import ABC, abstractmethod


class UsageBackend(ABC):
    """
    One quota backend = one compute model. Method signatures deliberately
    mirror the parameters the existing classic functions already take
    (host/token/logger, a peewee db handle, a date) rather than hiding them,
    so ClassicBackend can be a thin, provably-unchanged wrapper around
    today's code instead of a rewrite.
    """

    @abstractmethod
    def collect_and_enforce(self):
        """
        One polling cycle: collect current usage, update the DB, and act on
        any threshold crossed (warn, or block/terminate). Called periodically
        by cron via poll_clusters.py.
        """
        raise NotImplementedError

    @abstractmethod
    def restore(self, host, token, logger):
        """
        Undo any blocking enforcement action (e.g. restore cluster
        permissions, or -- serverless -- restore group membership) so the new
        day starts unblocked. Called once per day by end_of_day_operations.py,
        before the daily roll-up.
        """
        raise NotImplementedError

    @abstractmethod
    def roll_up_and_reset(self, prod_db, logger):
        """
        Archive the prior day's live usage into the historical/cumulative
        table and clear the live table for a fresh day. Called once per day
        by end_of_day_operations.py.
        """
        raise NotImplementedError

    @abstractmethod
    def report(self, when) -> str:
        """
        Build the HTML daily usage report for date `when`. Called once per
        day by end_of_day_operations.py before emailing it out.
        """
        raise NotImplementedError
