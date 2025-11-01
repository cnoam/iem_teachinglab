#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each     = toset(var.group_names)
  display_name = each.key
}

#
# Create a group for all student groups
#
resource "databricks_group" "all_student_groups" {
  display_name          = var.all_student_groups_name
  databricks_sql_access = var.databricks_sql_access
  workspace_access      = var.workspace_access
}

#
# Assign users to their respective groups
#
resource "databricks_group_member" "student_assignments" {
  for_each = {
    for m in var.group_members : "${m.group_name}_${m.member_name}" => m
  }

  group_id  = databricks_group.student_groups[each.value.group_name].id
  member_id = var.users[each.value.member_name].id
}

#
# Add all user groups to the "all_students" group
#
resource "databricks_group_member" "all_students_group_assignment" {
  for_each = databricks_group.student_groups

  group_id  = databricks_group.all_student_groups.id
  member_id = each.value.id
}