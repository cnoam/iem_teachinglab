#
# Schemas (Unity Catalog)
#
# Creates a Schema (Database) for each student group.
# Only enabled if var.enable_unified_catalog_isolation is true.
#
resource "databricks_schema" "group_schemas" {
  for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}

  catalog_name = var.catalog_name
  name         = each.value.schema_name
  comment      = "Dedicated schema for ${each.value.schema_name}"
}



#
# Grants for the Schemas:
#
# Ideally, the grants would be to group_NN but  DBR does not propagate the grant from group to user
# so we grant the users directly
