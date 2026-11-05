#
# Dedicated admin-only SQL warehouse for dbr_admin's scheduled system-table checks:
#   - billing backstop (dbr_admin/resource_manager/serverless_billing.py, SERVERLESS_BILLING_WAREHOUSE_ID)
#   - GPU usage alert   (dbr_admin/resource_manager/gpu_alert.py,      GPU_ALERT_WAREHOUSE_ID)
# Both scripts stop the warehouse right after their query (cuts cost), which is only
# safe because no student can use it. So: NO databricks_permissions here -- only the owner
# (the identity running terraform) and workspace admins can use it. Never grant
# students CAN_USE on this warehouse.
#
resource "databricks_sql_endpoint" "admin_checks" {
  name                      = "Admin Checks (no students)"
  cluster_size              = "2X-Small"
  min_num_clusters          = 1
  max_num_clusters          = 1
  auto_stop_mins            = 5 # backstop only -- the scripts stop it explicitly
  enable_serverless_compute = true
  warehouse_type            = "PRO"
}

output "admin_checks_warehouse_id" {
  description = "Set as SERVERLESS_BILLING_WAREHOUSE_ID and GPU_ALERT_WAREHOUSE_ID in dbr_admin/.env"
  value       = databricks_sql_endpoint.admin_checks.id
}
