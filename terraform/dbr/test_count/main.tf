

terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }
}


# Read the CSV file using data source
data "local_file" "user_names" {
  #filename = var.user_names_file   # get the file name from user
  filename = "./users.csv" 
}

# Decode the CSV content
locals {
  # Parse the CSV into a list of maps, where each map is a group of students
  groups = csvdecode(data.local_file.user_names.content)
  
  # Generate group names like "group_01", "group_02", etc.
  group_names = [for i in range(length(local.groups)) : format("group_%02d", i + 1)]


  group_members_flattened = flatten( [
    for idx, group in local.groups : [
      for member in group : {
        group_name = local.group_names[idx]
        member_name = trimspace(member)
      }if trimspace(member) != ""  # Filter out empty member names
    ]
  ])
}

#
# Create groups
#
resource "databricks_group" "student_groups" {
  for_each = toset(local.group_names)
  display_name = each.key
}

#
# Create users
#
resource "databricks_user" "workspace_user" {
  for_each     = { 
    for member in local.group_members_flattened: 
    "${member.group_name}_${member.member_name}" => member 
  }
  user_name    = each.value.member_name
  workspace_access = false
  active = false
}

#
# Assign users to their respective groups
#
resource "databricks_group_member" "student_assignments" {
  for_each = {
      for m in local.group_members_flattened: "${m.group_name}__${m.member_name}" => m
  }
  
  group_id  =  databricks_group.student_groups[each.value.group_name].id

  # Assign each member to the group using their ID
  member_id = databricks_user.workspace_user["${each.value.group_name}_${each.value.member_name}"].id
}



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
    first_on_demand = 1
    availability    = "ON_DEMAND_AZURE"
    spot_bid_max_price = -1
  }

  node_type_id          = "Standard_DS3_v2"
  driver_node_type_id   = "Standard_DS3_v2"
  ssh_public_keys       = []
  custom_tags           = {"origin" = "terraform"}

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
  is_pinned = true

  # After the cluster is created, it is in RUNNING state until the autotermination.
  # Since we don't need it running now, turn it off using REST API.

  # Add a local-exec provisioner to terminate the cluster immediately after creation
  provisioner "local-exec" {
    command = <<EOT
      curl -X POST https://${var.databricks_host}/api/2.0/clusters/delete \
      -H "Authorization: Bearer ${var.databricks_token}" \
      -d '{"cluster_id": "${self.id}"}'
    EOT
  }
}


#
# Assign each group to a cluster
#
# group "group_01" shall be assigned to "cluster_01" etc.
resource "databricks_permissions" "cluster_permissions" {
  for_each = databricks_group.student_groups
  cluster_id = databricks_cluster.clusters[replace(each.key, "group", "cluster")].id

  access_control {
    group_name = each.key
    permission_level = "CAN_RESTART"
  }
}
