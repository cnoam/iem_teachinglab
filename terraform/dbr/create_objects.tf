#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each     = toset(local.group_names)
  display_name = each.key
}

#
# Create users
# Users are keyed ONLY by their e-mail. This separation cleans the code
# and allows more flexible memberships
#
resource "databricks_user" "workspace_user" {
  for_each         = toset([for m in local.group_members_flattened : m.member_name])
  user_name        = each.key
  workspace_access = false
  active           = true
}
