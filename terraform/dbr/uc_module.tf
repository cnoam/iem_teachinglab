module "uc_setup" {
  source = "./modules/unified_catalog_setup"
  count  = var.enable_unified_catalog_isolation ? 1 : 0

  group_configs           = local.group_configs
  student_groups_csv_rows = local.groups
  group_members_flattened = local.group_members_flattened
  all_student_groups_name = databricks_group.all_student_groups.display_name

  catalog_name       = var.catalog_name
  sql_warehouse_name = var.sql_warehouse_name
  key_vault_name     = var.key_vault_name
  key_vault_rg       = var.key_vault_rg
  databricks_host    = data.databricks_current_config.this.host

  cluster_ids = { for k, v in databricks_cluster.clusters : k => v.id }

  # Dependencies passed as lists to ensure ordering if used, 
  # but mainly explicit depends_on below handles it.
  user_ids          = [for u in databricks_user.workspace_user : u.id]
  student_group_ids = [for g in databricks_group.student_groups : g.id]

  depends_on = [
    databricks_group.student_groups,
    databricks_user.workspace_user,
    databricks_cluster.clusters,
    databricks_group.all_student_groups,
    databricks_group_member.student_assignments,
    databricks_group_member.all_students_group_assignment
  ]
}
