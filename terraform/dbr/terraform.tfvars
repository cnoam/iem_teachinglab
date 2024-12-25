max_workers = 4


# Using env vars:
# Use the TF_VAR_ prefix followed by the exact name of your Terraform variable.

# for example
#  export TF_VAR_databricks_token=$DATABRICKS_TOKEN

# FUTURE:
# Specify which profile to use.
# This can also be done using env variable:
# export TF_VAR_databricks_profile=workspace1
# databricks_profile = "lab94290-integration-test"
# other profiles (defined in ~/.databrickscfg )
# profile = "lab94290"
# profile = "lab96224"
# profile = "lab96224-integration-test"