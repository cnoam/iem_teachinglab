#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each     = toset(local.group_names)
  display_name = each.key
}

#
# Create users
#
resource "databricks_user" "workspace_user" {
  for_each = {
    for member in local.group_members_flattened :
    "${member.group_name}_${member.member_name}" => member
  }
  user_name        = each.value.member_name
  workspace_access = false
  active           = true
}

