#
# Create a group for all student groups
#
resource "databricks_group" "all_student_groups" {
  display_name          = "all_student_groups"
  databricks_sql_access = true
  workspace_access      = true
}


#
# Assign users to their respective groups
#
resource "databricks_group_member" "student_assignments" {
  for_each = {
    for m in local.group_members_flattened : "${m.group_name}_${m.member_name}" => m
  }

  group_id = databricks_group.student_groups[each.value.group_name].id

  # Assign each member to the group using their ID
  member_id = databricks_user.workspace_user["${each.value.member_name}"].id
}


#
# Add all user groups to the "all_students" group
#
resource "databricks_group_member" "all_students_group_assignment" {
  for_each = databricks_group.student_groups

  group_id  = databricks_group.all_student_groups.id
  member_id = each.value.id
}