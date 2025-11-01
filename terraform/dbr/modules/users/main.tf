#
# Create users
# Users are keyed ONLY by their e-mail. This separation cleans the code
# and allows more flexible memberships
#
resource "databricks_user" "workspace_user" {
  for_each         = toset(var.users)
  user_name        = each.key
  workspace_access = var.workspace_access
  active           = var.active
}