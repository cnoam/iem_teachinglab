#!/bin/bash -eu

# Enforce sourcing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "This script must be sourced. Use: source ${BASH_SOURCE[0]}"
  return 1 2>/dev/null || exit 1
fi

# lab 94290
#export TF_VAR_databricks_token=
#export TF_VAR_databricks_host=


# lab96224 2025-04-10
export TF_VAR_databricks_token=*****
export TF_VAR_databricks_host=adb-***.azuredatabricks.net

export TF_CLI_ARGS_apply="-parallelism=200"
