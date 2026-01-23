max_workers   = 4
spark_version = "15.4.x-cpu-ml-scala2.12"


# Using env vars:
# Use the TF_VAR_ prefix followed by the exact name of your Terraform variable.

# for example
#  export TF_VAR_databricks_token=$DATABRICKS_TOKEN

python_packages = []
#"spark-nlp" ,"nltk"]


# declare what are the known DataBricks profiles.
# This is used to bind the correct DBR profile with the TF workspace
# key is TF workspace name
# value is DBR profile name. They do not have to be identical
workspace_profiles = {
  dev        = "dev_profile"
  lab94290w3 = "lab94290w3"
}

enable_unified_catalog_isolation = false

maven_packages = {}
