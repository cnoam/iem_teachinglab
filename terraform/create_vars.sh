#!/bin/bash -eu

# Enforce sourcing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "This script must be sourced. Use: source ${BASH_SOURCE[0]}"
  return 1 2>/dev/null || exit 1
fi

export TF_VAR_databricks_token=oops
export TF_VAR_databricks_host=oops

export TF_CLI_ARGS_apply="-parallelism=200"
