"""
Normalizes a Databricks host string so it always has a scheme, regardless
of whether the caller already added one.

DATABRICKS_HOST is stored without a scheme (e.g. "adb-123.4.azuredatabricks.net").
`databricks.sdk.WorkspaceClient` normalizes this itself, so as of the
2026-09-16 SDK migration none of the serverless_*.py modules need this
anymore. The one remaining caller is `backends/serverless.py`, for
constructing `DataBricksGroups` (used by group_map.py): it's built on
`databricks_cli`'s `ApiClient`, which -- unlike WorkspaceClient -- requires
an explicit scheme, and historically different call sites in this codebase
have prepended "https://" inconsistently (classic's
restore_cluster_permissions() callers do it; end_of_day_operations.py used
to pass the raw env var straight through to ServerlessBackend.restore()
before that was fixed). Use this function anywhere a raw host string is
about to be handed to `DataBricksGroups` or `DataBricksClusterOps`.
"""


def normalize_dbr_host(host: str) -> str:
    if not host:
        return host
    return host if host.startswith('http://') or host.startswith('https://') else f'https://{host}'
