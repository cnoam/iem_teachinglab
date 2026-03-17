#!/usr/bin/env bash
# Verifies that cloud-init has created the expected users on every team VM.
# Run this AFTER 'terraform apply' and BEFORE 'terraform destroy'.
#
# Usage:
#   cd terraform/provision_VM
#   bash tests/verify_ssh.sh
#
# Prerequisites: terraform apply has been run, id_rsa_lab.pem exists,
#                and jq is installed.

set -euo pipefail
set -x

KEY="./id_rsa_lab.pem"
SSH_OPTS="-i $KEY -o StrictHostKeyChecking=no   -o IdentitiesOnly=yes -o ConnectTimeout=5"
MAX_RETRIES=20
RETRY_SLEEP=15

if [[ ! -f "$KEY" ]]; then
  echo "ERROR: $KEY not found. Run 'terraform apply' first." >&2
  exit 1
fi

IPS=$(terraform output -json team_public_ip_addresses 2>/dev/null)
if [[ -z "$IPS" || "$IPS" == "{}" ]]; then
  echo "ERROR: No IPs found in terraform output. Has 'terraform apply' been run?" >&2
  exit 1
fi

TEAMS=$(echo "$IPS" | jq -r 'keys[]')
FAILURES=0

for TEAM in $TEAMS; do
  IP=$(echo "$IPS" | jq -r --arg t "$TEAM" '.[$t]')
  echo "--- $TEAM ($IP): waiting for SSH..."

  SUCCESS=false
  for i in $(seq 1 $MAX_RETRIES); do
    if ssh $SSH_OPTS vmadmin@"$IP" 'id vmadmin && id azureuser' 2>/dev/null; then
      echo "  OK: vmadmin and azureuser exist."
      SUCCESS=true
      break
    fi
    echo "  Attempt $i/$MAX_RETRIES failed, retrying in ${RETRY_SLEEP}s..."
    sleep $RETRY_SLEEP
  done

  if [[ "$SUCCESS" == "false" ]]; then
    echo "  FAIL: Could not verify users on $TEAM after $MAX_RETRIES attempts." >&2
    FAILURES=$((FAILURES + 1))
  fi
done

if [[ $FAILURES -gt 0 ]]; then
  echo ""
  echo "FAILED: $FAILURES team(s) did not pass SSH verification." >&2
  exit 1
fi

echo ""
echo "All teams passed SSH verification."
