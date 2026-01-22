#
# Create Clusters
#
resource "databricks_cluster" "clusters" {

  for_each = local.group_configs

  cluster_name = each.value.cluster_name

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

  node_type_id        = "Standard_DS3_v2"
  driver_node_type_id = "Standard_DS3_v2"
  ssh_public_keys     = []
  custom_tags         = { "origin" = "terraform" }

  cluster_log_conf {
    dbfs {
      destination = "dbfs:/cluster-logs"
    }
  }

  spark_env_vars = {
    "PYSPARK_PYTHON" = "/databricks/python3/bin/python3"
  }

  autotermination_minutes = var.autotermination_minutes
  enable_elastic_disk     = true
  data_security_mode      = "NONE"
  runtime_engine          = "STANDARD"
  is_pinned               = true

}
