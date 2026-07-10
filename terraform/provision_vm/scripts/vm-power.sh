#!/usr/bin/env bash
# Start or deallocate all VMs of a course, based on the terraform state.
#
# VMs are addressed by full Azure resource ID (which embeds the subscription),
# so this works no matter which subscription `az` currently defaults to.
#
# Run from a course folder (e.g. courses/95219) after `terraform apply`:
#   ../../scripts/vm-power.sh start    # boot all VMs and wait until running (ready for ansible)
#   ../../scripts/vm-power.sh stop     # deallocate all VMs (no billing), returns immediately
set -euo pipefail

usage() { echo "Usage: $0 start|stop   (run inside a course folder)"; exit 1; }
[[ $# -eq 1 ]] || usage
action=$1
[[ $action == start || $action == stop ]] || usage

command -v jq >/dev/null || { echo "ERROR: jq is required" >&2; exit 1; }

# Full resource IDs of every VM in the state (searches nested modules too).
mapfile -t ids < <(terraform show -json | jq -r '
  [.. | .resources? // empty | .[]
   | select(.type == "azurerm_linux_virtual_machine")
   | .values.id] | sort | .[]')

[[ ${#ids[@]} -gt 0 ]] || { echo "ERROR: no VMs in terraform state — run from a course folder after apply" >&2; exit 1; }

[[ $action == stop ]] && verb=Deallocating || verb=Starting
echo "$verb ${#ids[@]} VM(s):"
printf '  %s\n' "${ids[@]##*/}"

if [[ $action == stop ]]; then
  # Deallocate (not just power off) so compute is not billed; fire and forget.
  # NB: --no-wait must come before --ids.
  az vm deallocate --no-wait -o none --ids "${ids[@]}"
  echo "Deallocation requested for all VMs (running in background on Azure side)."
else
  # az vm start returns only when every VM is running.
  az vm start --only-show-errors --ids "${ids[@]}"
  echo "All VMs are running — you can run the ansible playbook now."
fi
