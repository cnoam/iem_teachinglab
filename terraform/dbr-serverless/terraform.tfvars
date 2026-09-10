workspace_profiles = {
  "prod" = "94290_2026" # matches the profile in ~/.databrickscfg for the real course workspace
}

catalog_name       = "94290_lab" # existing UC catalog in this workspace (see: databricks catalogs list)
sql_warehouse_name = "Shared Student Warehouse"

enable_unified_catalog_isolation = true

# Shared read-only course dataset -- see docs/course_data_storage_setup.md
course_data_storage_account     = "lab94290"
course_data_containers          = ["airbnb", "booking"]
course_data_access_connector_id = "/subscriptions/b3931bf1-b901-4dc2-bf3e-b020fa67cb8b/resourcegroups/databricks-rg-94290-lab-c42ettx4sl3ns/providers/Microsoft.Databricks/accessConnectors/unity-catalog-access-connector"
