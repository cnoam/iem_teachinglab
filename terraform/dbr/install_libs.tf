
# Install required libraries to the Workspace, so they are available to call clusters
# see https://registry.terraform.io/providers/databricks/databricks/latest/docs/resources/library

# If need to install multiple libs, change to using variable lists
data "databricks_clusters" "all" {
  depends_on = [databricks_cluster.clusters]
}

# Install Maven Library
resource "databricks_library" "maven_library" {
  for_each   = data.databricks_clusters.all.ids  # To install lib, you need the cluster to exist (and turned on)
  cluster_id = each.key
  maven {
    coordinates = "com.johnsnowlabs.nlp:spark-nlp_2.12:4.4.2" # Replace with the required version
    repo        = "https://maven.johnsnowlabs.com"
  }
}

# #
# # for debugging, limit the scope to a single cluster
# #
# data "databricks_cluster" "details" {
#   for_each = toset(data.databricks_clusters.all.ids)
#   cluster_id = each.value
# }
#
# resource "databricks_library" "maven_library" {
#   for_each = {
#     for id, details in data.databricks_cluster.details : id => details
#     if details.cluster_name == "cluster_03"
#   }
#   cluster_id = each.key
#
#   maven {
#     coordinates = "com.johnsnowlabs.nlp:spark-nlp_2.12:4.4.2" # Replace with the required version
#     repo        = "https://maven.johnsnowlabs.com"
#   }
# }

# # Install Python Library for Glue
resource "databricks_library" "python_glue_library" {
  for_each   = data.databricks_clusters.all.ids

# For debugging, using also the code above, replace the above line with for_each{} below
#  for_each = {
#     for id, details in data.databricks_cluster.details : id => details
#     if details.cluster_name == "cluster_03"
#   }
  cluster_id = each.key
  pypi {
    package = "spark-nlp" # Python wrapper for JohnSnowLabs NLP
    #version = "4.4.2"     # Ensure this matches the Maven library version
  }
}
