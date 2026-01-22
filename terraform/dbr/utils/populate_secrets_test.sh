#!/bin/bash -eu

# run the script to test Vault usage. It will overwrite existing values
exit 1 # to make sure you don't run it by mistake after real values are stored.
# Configuration
KV_NAME="sp-secrets-94290"

echo "Populating $KV_NAME with dummy secrets for testing..."

# Loop for groups 01 to 03 (Expand to 30 as needed)
for i in {1..3}; do
  GROUP_NUM=$(printf "%02d" $i)
  SECRET_NAME="sp-secret-group-${GROUP_NUM}"
  SECRET_VALUE="dummy-secret-value-for-group-${GROUP_NUM}"
  
  echo "Setting secret: $SECRET_NAME"
  az keyvault secret set --vault-name "$KV_NAME" --name "$SECRET_NAME" --value "$SECRET_VALUE" --output none
done

echo "Done! Run 'terraform apply' to verify retrieval."
