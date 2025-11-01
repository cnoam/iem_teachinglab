#
# Create Clusters
#
resource "databricks_cluster" "clusters" {
  for_each = {
    for group_name in var.group_names :
    replace(group_name, "group", "cluster") => group_name
  }

  cluster_name = each.key

  spark_version = var.spark_version

  autoscale {
    min_workers = var.min_workers
    max_workers = var.max_workers
  }

  spark_conf = {
    "spark.databricks.delta.preview.enabled" = "true"
  }

  azure_attributes {
    first_on_demand    = 1
    availability       = "ON_DEMAND_AZURE"
    spot_bid_max_price = -1
  }

  node_type_id        = var.node_type_id
  driver_node_type_id = var.driver_node_type_id
  ssh_public_keys     = []
  custom_tags         = var.custom_tags

  cluster_log_conf {
    dbfs {
      destination = var.cluster_log_destination
    }
  }

  spark_env_vars = {
    "PYSPARK_PYTHON" = var.pyspark_python
  }

  autotermination_minutes = var.autotermination_minutes
  enable_elastic_disk     = var.enable_elastic_disk
  data_security_mode      = var.data_security_mode
  runtime_engine          = var.runtime_engine
  is_pinned               = var.is_pinned
}