
# Install required libraries to the Workspace, so they are available to call clusters
# see https://registry.terraform.io/providers/databricks/databricks/latest/docs/resources/library


# If need to install multiple libs, change to using variable lists
# data "databricks_clusters" "all" {
#   depends_on = [databricks_cluster.clusters]
# }

# Install Maven Library
resource "databricks_library" "maven_library" {
 for_each = databricks_cluster.clusters
 cluster_id = each.value.id
 maven {
   coordinates = "com.johnsnowlabs.nlp:spark-nlp_2.12:5.5.2"
   repo        = "https://maven.johnsnowlabs.com"
 }
}



# Install Python Library for Glue
resource "databricks_library" "python_glue_library" {

 for_each = databricks_cluster.clusters
  cluster_id = each.value.id
  pypi {
   package = "spark-nlp" # Python wrapper for JohnSnowLabs NLP
  }
}
