#!/bin/bash -eu
set -euo pipefail

# This script reads a CSV file containing manually generated Databricks Service Principal secrets
# and populates them into an Azure Key Vault.
# It is needed because the account admin refuse to grant me permission to generate secrets directly using TF.
#
# LIMITATION: up to 99 groups

# --- Configuration ---
KV_NAME="sp-secrets-94290"

# --- Functions ---
usage() {
  echo "Usage: $0 <path_to_csv_file> [--overwrite]"
  echo
  echo "  <path_to_csv_file> : CSV file with two columns: 'group_number,secret_value'."
  echo "  --overwrite        : Optional. Overwrites secrets if they already exist in the Key Vault."
  echo
  echo "Example CSV format:"
  echo "01,dapi-xxxxxxxxxxxxxxxxxxxxxxxx"
  echo "02,dapi-yyyyyyyyyyyyyyyyyyyyyyyy"
}

# --- Main Script ---

# 1. Argument Parsing
if [[ $# -lt 1 || "$1" == "--help" ]]; then
  usage
  exit 0
fi

CSV_FILE="$1"
OVERWRITE=${2:-""}

if [[ ! -f "$CSV_FILE" ]]; then
  echo "Error: File not found at '$CSV_FILE'"
  usage
  exit 1
fi

# 2. Prerequisites Check
if ! command -v az &> /dev/null; then
  echo "Error: 'az' CLI is not installed. Please install Azure CLI."
  exit 1
fi
# Check if logged in
az account show &> /dev/null
if [ $? -ne 0 ]; then
  echo "Error: Not logged into Azure. Please run 'az login'."
  exit 1
fi

echo "Using Key Vault: $KV_NAME"
echo "Reading secrets from: $CSV_FILE"
echo "---"

# 3. Read CSV and process secrets
# Use a while loop to read line-by-line, handling potential spaces
# The `|| [[ -n "$line" ]]` handles the case where the last line doesn't have a newline
while IFS=, read -r group_num secret_val || [[ -n "$group_num" ]]; do
 
  SECRET_NAME="sp-secret-group-${group_num}"

  # Trim whitespace from variables
  GROUP_RAW=$(echo "$group_num" | xargs)
  SECRET_VALUE=$(echo "$secret_val" | xargs)

  # Skip header or empty lines
  if [[ -z "$GROUP_RAW" || "$GROUP_RAW" == "group_number" ]]; then
    continue
  fi

  # Normalize group number so "1" and "01" are treated identically (canonical: two digits)
  # Accepts 1..99, rejects 0, 00, 100, non-numeric, etc.
  if ! [[ "$GROUP_RAW" =~ ^[0-9]{1,2}$ ]]; then
    echo "Error: invalid group_number '$GROUP_RAW' (expected 1..99 or 01..99)" >&2
    exit 1
  fi

  GROUP_INT=$((10#$GROUP_RAW))  # 10# prevents octal interpretation for values like 08/09
  if (( GROUP_INT < 1 || GROUP_INT > 99 )); then
    echo "Error: group_number out of range '$GROUP_RAW' (expected 1..99)" >&2
    exit 1
  fi

  GROUP_NUM=$(printf "%02d" "$GROUP_INT")


  # Check if secret exists
  if az keyvault secret show --vault-name "$KV_NAME" --name "$SECRET_NAME" &> /dev/null; then
    # Secret exists
    if [[ "$OVERWRITE" == "--overwrite" ]]; then
      echo "[UPDATE] Overwriting secret: $SECRET_NAME"
      az keyvault secret set --vault-name "$KV_NAME" --name "$SECRET_NAME" --value "$SECRET_VALUE" --output none
    else
      echo "[SKIP] Secret '$SECRET_NAME' already exists. Use --overwrite to force."
    fi
  else
    # Secret does not exist
    echo "[CREATE] Setting new secret: $SECRET_NAME"
    az keyvault secret set --vault-name "$KV_NAME" --name "$SECRET_NAME" --value "$SECRET_VALUE" --output none
  fi

done < "$CSV_FILE"

echo "---"
echo "Done! Key Vault population complete."
