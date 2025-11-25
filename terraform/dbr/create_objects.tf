#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each     = toset(local.group_names)
  display_name = each.key
  # Set to false to prevent members of this group from creating unrestricted clusters
  allow_cluster_create = false
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

# -- disable user ability to create personal clusters --
resource "databricks_cluster_policy" "personal_compute" {
  name = "Personal Compute"
  description = "NC use with small-to-medium data or libraries like pandas and scikit-learn. Spark runs in local mode."
  policy_family_id = "personal-vm"
  policy_family_definition_overrides = jsonencode(
    {"node_type_id": {
      "type": "forbidden" 
      }
    })
}
