
#
# Assign users to their respective groups
#
resource "databricks_group_member" "student_assignments" {
  for_each = {
      for m in local.group_members_flattened: "${m.group_name}__${m.member_name}" => m
  }
  
  group_id  =  databricks_group.student_groups[each.value.group_name].id

  # Assign each member to the group using their ID
  member_id = databricks_user.workspace_user["${each.value.group_name}_${each.value.member_name}"].id
}


#
# Assign each group to a cluster
#
# group "group_01" shall be assigned to "cluster_01" etc.
resource "databricks_permissions" "cluster_permissions" {
  for_each = databricks_group.student_groups
  cluster_id = databricks_cluster.clusters[replace(each.key, "group", "cluster")].id

  access_control {
    group_name = each.key
    permission_level = "CAN_RESTART"
  }
}
