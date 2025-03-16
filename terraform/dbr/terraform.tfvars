max_workers   = 4
spark_version = "15.4.x-cpu-ml-scala2.12"


# Using env vars:
# Use the TF_VAR_ prefix followed by the exact name of your Terraform variable.

# for example
#  export TF_VAR_databricks_token=$DATABRICKS_TOKEN


# Specify which profile to use.
# This can also be done using env variable:
# export TF_VAR_databricks_profile=lab94290
databricks_profile = "lab96224"

# profiles are defined in ~/.databrickscfg

python_packages = ["spark-nlp" ,"nltk"]
