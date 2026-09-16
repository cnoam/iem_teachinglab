"""
Serverless backend -- not yet implemented.

See databricks/serverless_quota_plan.md for the full design; this stub is
Step 1's placeholder. Step 2 of that plan fills these methods in with the
query-history ingest, union-of-intervals aggregation, and the group-removal
enforcement lever (confirmed live-tested, see the plan's section 2.5).
"""
from .base import UsageBackend

_NOT_IMPLEMENTED = (
    "Serverless quota backend is not implemented yet. "
    "See databricks/serverless_quota_plan.md."
)


class ServerlessBackend(UsageBackend):
    """Placeholder. QUOTA_MODE=serverless currently raises NotImplementedError."""

    def collect_and_enforce(self):
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def restore(self, host, token, logger):
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def roll_up_and_reset(self, prod_db, logger):
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def report(self, when) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)
