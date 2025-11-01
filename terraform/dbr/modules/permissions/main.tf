#
# Assign each group to a cluster
#
# group "group_01" shall be assigned to "cluster_01" etc.
resource "databricks_permissions" "cluster_permissions" {
  for_each   = var.student_groups
  cluster_id = var.clusters[replace(each.key, "group", "cluster")].id

  access_control {
    group_name       = each.key
    permission_level = var.permission_level
  }
}