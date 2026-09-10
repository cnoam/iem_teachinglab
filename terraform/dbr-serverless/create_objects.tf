#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each     = { for k, v in local.group_configs : v.group_name => v }
  display_name = each.key
  # Prevent students from creating classic clusters; they should use serverless.
  allow_cluster_create = false
}

#
# Create users
#
resource "databricks_user" "workspace_user" {
  for_each         = toset([for m in local.group_members_flattened : m.member_name])
  user_name        = each.key
  workspace_access = false
  active           = true
}

# Prevent students from launching classic personal clusters.
resource "databricks_cluster_policy" "personal_compute" {
  name             = "Personal Compute"
  description      = "use with small-to-medium data or libraries like pandas and scikit-learn. Spark runs in local mode."
  policy_family_id = "personal-vm"
  policy_family_definition_overrides = jsonencode(
    { "node_type_id" : {
      "type" : "forbidden"
      }
  })
}
