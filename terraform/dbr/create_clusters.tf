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

  spark_env_vars = {
    "PYSPARK_PYTHON" = "/databricks/python3/bin/python3"
  }

  autotermination_minutes = var.autotermination_minutes
  enable_elastic_disk     = true
  runtime_engine          = "STANDARD"
  is_pinned               = true

  # Dedicated cluster shared by the whole group (DBR 15.4+, UC-enabled workspace).
  # Group members share one identity's permissions, so no isolation between them is
  # needed -- only isolation *between* groups, which is already given by one cluster
  # per group. Dedicated mode (unlike USER_ISOLATION/Shared) supports the ML runtime,
  # so MLlib classes like StringIndexer aren't blocked by the Py4J security manager.
  kind               = "CLASSIC_PREVIEW"
  data_security_mode = "DATA_SECURITY_MODE_DEDICATED"
  use_ml_runtime     = true
  single_user_name   = each.value.group_name

  depends_on = [databricks_group.student_groups]
}
