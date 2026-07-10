#!/usr/bin/env bash
# Full provisioning cycle for one course:
#   1. terraform apply          (interactive — you approve the plan)
#   2. vm-power.sh start        (make sure every VM is up)
#   3. ansible deploy-keys.yml  (skipped for entra courses — not needed)
#   4. vm-power.sh stop         (deallocate so nothing is billed; skip with --keep-running)
#
# Usage:
#   ./provision-course.sh courses/95219 [--keep-running]
#   or run with no course argument from inside a course folder.
set -euo pipefail

script_dir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)  # real scripts/ dir, even when called via symlink
vm_power="$script_dir/vm-power.sh"
playbook="$script_dir/../ansible/playbooks/deploy-keys.yml"

course_dir=$PWD
keep_running=0
for arg in "$@"; do
  case $arg in
    --keep-running) keep_running=1 ;;
    -h|--help) sed -n '2,/^[^#]/{s/^# \{0,1\}//p}' "$0"; exit 0 ;;
    *) course_dir=$arg ;;
  esac
done

[[ -f $course_dir/main.tf ]] || { echo "ERROR: $course_dir is not a course folder (no main.tf). Pass one, e.g. courses/95219" >&2; exit 1; }
cd "$course_dir"

echo "==> [1/4] terraform apply ($PWD)"
terraform apply

echo "==> [2/4] starting all VMs"
"$vm_power" start

auth_method=$(terraform output -raw auth_method 2>/dev/null || echo deploykey)
if [[ $auth_method == entra ]]; then
  echo "==> [3/4] auth_method=entra — no key deployment needed, skipping ansible"
else
  echo "==> [3/4] deploying SSH keys via ansible"
  ansible-playbook "$playbook"
fi

if [[ $keep_running -eq 1 ]]; then
  echo "==> [4/4] --keep-running: leaving VMs up (remember to '$vm_power stop' later)"
else
  echo "==> [4/4] deallocating all VMs"
  "$vm_power" stop
fi

echo "Done."
