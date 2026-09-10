#
# Shared read-only course dataset (Unity Catalog external volumes).
# See ../docs/course_data_storage_setup.md for the full history, the Azure RBAC
# prerequisites (Storage Blob Data Reader + Storage Blob Delegator on the access
# connector identity, per container), and why each piece below is needed.
#
# Grants go to each student's email individually, not to a workspace-local group
# (all_student_groups) -- confirmed 2026-09-10 that group-based grants are silently
# accepted but do not actually resolve for volumes/external locations.
#

resource "databricks_storage_credential" "course_data_credential" {
  name      = "course_data_credential"
  read_only = true
  comment   = "Dedicated non-default credential for the shared read-only course dataset (lab94290: airbnb, booking)"

  azure_managed_identity {
    access_connector_id = var.course_data_access_connector_id
  }
}

resource "databricks_external_location" "course_data" {
  for_each = var.course_data_containers

  name            = "${each.key}_data"
  url             = "abfss://${each.key}@${var.course_data_storage_account}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.course_data_credential.name
  read_only       = true
}

resource "databricks_schema" "course_data" {
  catalog_name = var.catalog_name
  name         = "course_data"
  comment      = "Shared read-only course dataset schema"
}

resource "databricks_volume" "course_data" {
  for_each = var.course_data_containers

  catalog_name     = var.catalog_name
  schema_name      = databricks_schema.course_data.name
  name             = each.key
  volume_type      = "EXTERNAL"
  storage_location = databricks_external_location.course_data[each.key].url
}

resource "databricks_grants" "course_data_schema" {
  schema = "${var.catalog_name}.${databricks_schema.course_data.name}"

  dynamic "grant" {
    for_each = toset([for m in local.group_members_flattened : m.member_name])
    content {
      principal  = grant.value
      privileges = ["USE_SCHEMA"]
    }
  }
}

resource "databricks_grants" "course_data_volume" {
  for_each = var.course_data_containers

  volume = "${var.catalog_name}.${databricks_schema.course_data.name}.${each.key}"

  dynamic "grant" {
    for_each = toset([for m in local.group_members_flattened : m.member_name])
    content {
      principal  = grant.value
      privileges = ["READ_VOLUME"]
    }
  }
}

resource "databricks_grants" "course_data_external_location" {
  for_each = var.course_data_containers

  external_location = databricks_external_location.course_data[each.key].name

  dynamic "grant" {
    for_each = toset([for m in local.group_members_flattened : m.member_name])
    content {
      principal  = grant.value
      privileges = ["READ_FILES"]
    }
  }
}
