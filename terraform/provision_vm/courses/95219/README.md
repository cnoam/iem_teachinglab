[2026-09-10 ] Epilog after end of semester: The whole process was painful. too mauch manual handling (download googl sheet, deploy keys, update users.csv ...
I did not see a real gain from forcing them the actual usage of ssh keys.
**Recommendation** : Use the EntraID version!



# Course 95219 — Provisioning Checklist

Full runbook: [`../docs/student-ci-azure-admin-runbook.md`](../docs/student-ci-azure-admin-runbook.md).
This is just the short checklist for this course folder.

## 1. Roster
- [ ] Fill `users.csv` (one row per group, columns = member emails) — see `users.csv.example`

## 2. Collect student deploy keys
- [ ] Students submit `group_id` + pubkey via the shared spreadsheet
- [ ] Export the spreadsheet to CSV
- [ ] Run the parser from this directory:
  ```bash
  python ../../ansible/scripts/parse_student_keys.py <exported.csv>
  ```
  → writes `keys/group_01.pub`, … (gitignored)
- [ ] Sanity-check any doubtful key:
  ```bash
  ssh-keygen -l -f keys/group_NN.pub
  ```

## 3. Provision VMs
- [ ] `terraform.tfvars` has `subscription_id` (or pass `-var="subscription_id=<id>"`)
- [ ] `terraform init`
- [ ] `terraform apply`

## 4. Deploy keys to VMs
- [ ] `ansible-playbook ../../ansible/playbooks/deploy-keys.yml` (all groups)
  - or `-l <host>` for a single group

## 5. Ongoing key management
- [ ] Rotate a group's key: replace their `.pub` in `keys/`, re-run the playbook
- [ ] Revoke a group: replace their `.pub` with an empty file, re-run the playbook

## Convenience script
`../scripts/provision-course.sh` automates steps 3–4 (apply → start VMs →
deploy keys → stop VMs). It assumes `keys/*.pub` already exist — run step 2
first.
