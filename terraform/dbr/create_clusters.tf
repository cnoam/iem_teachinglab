#
# Create Clusters
#
resource "databricks_cluster" "clusters" {
  #  count = length(local.groups)
  #  cluster_name = "cluster_${count.index + 1}"

  #  for_each = toset(local.group_names) # Iterate over group names
  #  cluster_name = replace(each.key, "group", "cluster")


  for_each = {
    for group_name in local.group_names :
    replace(group_name, "group", "cluster") => group_name
  }


  cluster_name = each.key

  spark_version = "${var.spark_version}"

  autoscale {
    min_workers = "${var.min_workers}"
    max_workers = "${var.max_workers}"
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
  ssh_public_keys = []
  custom_tags = { "origin" = "terraform" }

  cluster_log_conf {
    dbfs {
      destination = "dbfs:/cluster-logs"
    }
  }

  spark_env_vars = {
    "PYSPARK_PYTHON" = "/databricks/python3/bin/python3"
  }

  autotermination_minutes = "${var.autotermination_minutes}"
  enable_elastic_disk     = true
  data_security_mode      = "NONE"
  runtime_engine          = "STANDARD"
  is_pinned               = true

}
