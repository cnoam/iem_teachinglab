# Clusters Module

This module creates Databricks clusters for each group.

## Variables

- `group_names` - List of group names used to create corresponding clusters
- `spark_version` - Spark version (default: "15.4.x-cpu-ml-scala2.12")
- `min_workers` - Minimal Worker node count (default: 1)
- `max_workers` - Max Worker node count (default: 6)
- `autotermination_minutes` - Auto termination [minutes] (default: 20)
- `node_type_id` - Node type ID for worker nodes (default: "Standard_DS3_v2")
- `driver_node_type_id` - Node type ID for driver node (default: "Standard_DS3_v2")
- `custom_tags` - Custom tags to apply to clusters (default: { "origin" = "terraform" })
- `cluster_log_destination` - Destination for cluster logs (default: "dbfs:/cluster-logs")
- `pyspark_python` - Python interpreter for PySpark (default: "/databricks/python3/bin/python3")
- `enable_elastic_disk` - Enable elastic disk for clusters (default: true)
- `data_security_mode` - Data security mode for clusters (default: "NONE")
- `runtime_engine` - Runtime engine for clusters (default: "STANDARD")
- `is_pinned` - Pin clusters to prevent automatic termination (default: true)

## Outputs

- `clusters` - Map of created clusters keyed by cluster name