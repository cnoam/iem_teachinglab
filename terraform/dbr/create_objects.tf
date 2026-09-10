#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each     = { for k, v in local.group_configs : v.group_name => v } # Index by "group_01", "group_02"
  display_name = each.key                                                # This will be "group_01", "group_02"
  # Set to false to prevent members of this group from creating unrestricted clusters
  allow_cluster_create = false
}

#
# Per-group service principal, used as the DEDICATED cluster's single_user_name.
# Databricks resolves single_user_name against account-level identities, and a
# workspace-local group (databricks_group) does not qualify -- see
# "Did not find account group assigned to workspace ... with name group_NN".
# A service principal, unlike a group, is itself a valid account-level identity.
#
resource "databricks_service_principal" "group_sps" {
  for_each = local.group_configs

  display_name = each.value.service_principal_name
  active       = true
}

#
# Create users
# Users are keyed ONLY by their e-mail. This separation cleans the code
# and allows more flexible memberships
#
resource "databricks_user" "workspace_user" {
  for_each  = toset([for m in local.group_members_flattened : m.member_name])
  user_name = each.key
  # Keep false: Databricks sends the SCIM invitation email only when a user is
  # provisioned WITH workspace access. Students log in via Entra ID role
  # assignment (see readme.md), so an invite email would only confuse them.
  workspace_access = false
  active           = true
}

# -- disable user ability to create personal clusters --
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
