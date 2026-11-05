#
# Service Principal Secrets
#
# Generates a secret for each SP automatically.
# WARNING: The secret value will be stored in the Terraform state.
# Requires Account Admin privileges on the Databricks account.
#
resource "databricks_service_principal_secret" "group_sp_secrets" {
  for_each = var.group_configs

  service_principal_id = databricks_service_principal.group_sps[each.key].id
  lifetime             = "15552000s" # 180 days -- must outlast the semester (2026-11 .. 2027-02); Go durations don't support "w"/"d"
}
