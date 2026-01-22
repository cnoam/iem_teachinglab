
# Install required libraries to the Workspace, so they are available to call clusters
# see https://registry.terraform.io/providers/databricks/databricks/latest/docs/resources/library



# Local variable to create unique keys for each cluster-library combination
locals {
  maven_library_map = flatten([
    for cluster_key, cluster_value in databricks_cluster.clusters : [
      for lib_key, lib_value in var.maven_packages : {
        key         = "${cluster_key}_${lib_key}"
        cluster_id  = cluster_value.id
        coordinates = lib_value.coordinates
        repo        = lib_value.repo
      }
    ]
  ])

  python_library_map = flatten([
    for cluster_key, cluster_value in databricks_cluster.clusters : [
      for lib_name in var.python_packages : {
        key        = "${cluster_key}_${lib_name}"
        cluster_id = cluster_value.id
        package    = lib_name
      }
    ]
  ])
}

# Convert the lists into maps with unique keys for each library
locals {
  maven_library_resources  = { for item in local.maven_library_map : item.key => item }
  python_library_resources = { for item in local.python_library_map : item.key => item }
}


# Resource to install Maven libraries
resource "databricks_library" "maven_library" {
  for_each   = local.maven_library_resources
  cluster_id = each.value.cluster_id
  maven {
    coordinates = each.value.coordinates
    repo        = each.value.repo
  }
}

# Resource to install Python libraries
resource "databricks_library" "python_library" {
  for_each   = local.python_library_resources
  cluster_id = each.value.cluster_id
  pypi {
    package = each.value.package
  }
}
