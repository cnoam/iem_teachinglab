#
# SQL Warehouse (Shared)
#
# Creates a single SQL Warehouse shared by all student groups.
# Only enabled if var.enable_unified_catalog_isolation is true.
#

resource "databricks_sql_endpoint" "shared_warehouse" {
  # Use count to toggle creation based on the variable (0 or 1)
  count = var.enable_unified_catalog_isolation ? 1 : 0

  name             = var.sql_warehouse_name
  cluster_size     = "2X-Small"
  max_num_clusters = 1
  auto_stop_mins   = 10

  # Serverless is often preferred if available, but "PRO" or "CLASSIC" are safer defaults for generic workspaces
  warehouse_type = "PRO"
}
