"""
Normalizes a Databricks host string so every caller gets a consistent,
request-ready URL, regardless of whether it already has a scheme.

DATABRICKS_HOST is stored without a scheme (e.g. "adb-123.4.azuredatabricks.net")
and different call sites in this codebase have historically prepended
"https://" inconsistently -- e.g. classic's restore_cluster_permissions()
callers do it, but end_of_day_operations.py passes the raw env var straight
through to ServerlessBackend.restore(). Rather than rely on every caller
getting this right, every function in the serverless_* modules that builds
a URL normalizes its own `host` argument via this function.
"""


def normalize_dbr_host(host: str) -> str:
    if not host:
        return host
    return host if host.startswith('http://') or host.startswith('https://') else f'https://{host}'
