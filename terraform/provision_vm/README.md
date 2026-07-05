# provision_vm

Provisions one Azure VM per student group from a roster CSV. Replaces the
former `provision_VM` (Entra) and `provision_VM_ssh` (deploy-key) projects with
a single shared module plus one thin root per course.

The two student-authentication methods are **mutually exclusive per course** —
each course picks one and never mixes them.

| | `auth_method = "entra"` | `auth_method = "deploy_key"` |
| --- | --- | --- |
| Student login | `az ssh vm` (Microsoft Entra) | plain SSH to `azureuser` with their key |
| Extra Azure resources | `AADSSHLoginForLinux` extension + `Virtual Machine User Login` role | none (keys pushed by Ansible) |
| Key distribution | Entra handles it | `parse_student_keys.py` → `deploy-keys.yml` |

Everything else — network, VM, daily + idle auto-shutdown, self-deallocate role,
`Reader` + `VM Contributor` RBAC, cloud-init (Docker, Azure CLI, idle-watcher),
`azureuser` student account — is identical and lives in the module.

## Layout

```
modules/team_vm/      shared infrastructure (the single source of truth)
ansible/              shared, course-agnostic playbooks + parser
  playbooks/{base_setup,lab_pg_vs_ch,deploy-keys}.yml
  scripts/parse_student_keys.py
courses/<course>/     one Terraform root = one state = one course
  main.tf  versions.tf  variables.tf  users.csv  terraform.tfvars
```

`courses/example-entra/` and `courses/example-deploykey/` are working templates.

## Concurrent courses

Each course is its own folder with its own state and its own on-disk artifacts
(`id_rsa_lab.pem`, `inventory.ini`, `keys/`). To stand up a new course:

1. `cp -r courses/example-entra courses/my-course` (or the deploy-key one).
2. Edit `courses/my-course/`:
   - `versions.tf` — set a **unique** backend `key`.
   - `main.tf` — set a **unique** `name_prefix` and any size/port options.
   - `users.csv` — the real roster (gitignored).
   - `terraform.tfvars` — `subscription_id` (gitignored).
3. `cd courses/my-course && terraform init && terraform apply`.

`name_prefix` and the backend `key` must be unique per course: the backend key
keeps state isolated, and `name_prefix` keys the subscription-scoped
self-deallocate role (collides otherwise).

## Provisioning a course

```bash
cd courses/my-course
terraform apply                                   # VMs created, powered ON

# Ansible is driven by the ansible.cfg Terraform generated in THIS folder.
# Always run it from inside the course folder.
ansible-playbook ../../ansible/playbooks/base_setup.yml
```

### deploy_key courses — install student keys

```bash
cd courses/my-course
python ../../ansible/scripts/parse_student_keys.py path/to/keys.csv   # -> keys/group_NN.pub
ansible-playbook ../../ansible/playbooks/deploy-keys.yml -l my-course-group_01
```

`deploy-keys.yml` is `exclusive: true` — it replaces `azureuser`'s
`authorized_keys`. Rotate by replacing `keys/group_NN.pub` and re-running;
revoke by replacing it with an empty file and re-running.

### entra courses — student connection

```bash
az login
az ssh vm -n <VM_RESOURCE_NAME> -g <RG>     # names from `terraform output`
```

## Cost control

- **Daily auto-shutdown** at `auto_shutdown_time` (default `2350` UTC).
- **In-guest idle-watcher** deallocates after `idle_shutdown_hours` (default 4)
  of low CPU load, via the VM's managed identity + the self-deallocate role.

Ansible can only reach a **running** VM, so run playbooks soon after `apply`, or
`az vm start` the VM first.

## Gotchas

- **Run ansible from inside the course folder.** A wrong folder uses that
  folder's inventory/keys; the `name_prefix`-prefixed host alias makes a
  wrong-target run visible in the play recap.
- **Backend keys can't be variables** — each `versions.tf` hard-codes a unique
  `key`. Don't reuse one across courses.
- **One VM per group** is the mainline. The old two-VMs-per-team variant, if
  ever needed, belongs on a branch — not a knob here.
