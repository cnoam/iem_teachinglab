---
doc_kind: ops
lifecycle: living
status: active
authority: source
scope: "Admin runbook — provision per-group Azure VMs and manage student deploy keys for the CI/CD assignment"
updated: 2026-07-05
---
# Admin Runbook: Per-Group Azure VMs for the CI/CD Assignment

Companion to [student-ci-azure-assignment.md](student-ci-azure-assignment.md).
This is the **admin-only** side: how *you* provision one VM per group, retain
access regardless of when students send their keys, and add/rotate/revoke each
group's deploy key in bulk.

---

Everything described here is implemented in
[`terraform/provision_vm`](../README.md): the shared module
[`modules/team_vm`](../modules/team_vm/) plus one thin Terraform root per course
under [`courses/`](../courses/). This document is the operating instructions;
the code is the source of truth for resource details.

---

## Model in one picture

```
You (admin)                          Each group's GitHub Actions
   │  id_rsa_lab.pem (TF-generated)        │  SSH_PRIVATE_KEY secret
   │                                       │
   ▼  user: vmadmin                        ▼  user: azureuser
┌──────────────────────────────────────────────┐
│  Azure VM  (one per group)                     │
│  NSG: 22 ← allowed_ssh_cidrs (default: world)  │
│       80  ← world (ACME / redirect)            │
│       443 ← world (the app)                    │
│  FQDN: <name_prefix>-<group-hyphens>.<region>.cloudapp.azure.com  │
│  vmadmin    → admin key (baked at provision)   │
│  azureuser  → group's key (added later)        │
└──────────────────────────────────────────────┘
```

- **`vmadmin`** is yours, injected by Terraform at VM creation. You are never
  locked out, even before any student sends a key.
- **`azureuser`** is the students' account. Their CI uses it. You populate its
  `authorized_keys` from the public keys groups send you.
- Two separate accounts → clean attribution and clean revocation.
- Port 22 is world-open by default because GitHub-hosted runners have no fixed
  IP; key-only auth is the control. Restrict with the module's
  `allowed_ssh_cidrs` if the course doesn't need CI over SSH.

---

## 1. The admin keypair

You don't create it — `terraform apply` generates an RSA keypair per course and
writes it into the course folder as `id_rsa_lab.pem` / `id_rsa_lab.pub`
(see [`modules/team_vm/main.tf`](../modules/team_vm/main.tf), "Bootstrap admin
keypair"). The public half is baked into every VM as `vmadmin`'s key; the
generated `inventory.ini` / `ansible.cfg` point at the `.pem` automatically.

Keep the `.pem` private (mode 0600, it's gitignored). **Never share it with
students** — it is root-equivalent on every group's VM.

---

## 2. Provision the VMs in bulk (Terraform)

One VM per group, driven by the course roster. All resources — network, NSG,
VM, RBAC, cost controls — live in the shared module
[`modules/team_vm`](../modules/team_vm/main.tf); a course root such as
[`courses/95219`](../courses/95219/main.tf) is just a module call with the
course's settings. Guest setup (Docker, the `azureuser` account, SSH hardening,
the idle watcher) is [`modules/team_vm/cloud-init.yaml`](../modules/team_vm/cloud-init.yaml).

For this assignment the course root must set `auth_method = "deploy_key"`,
`open_web_ports = true` (80/443 for Let's Encrypt + the app) and
`enable_fqdn = true` (a cert cannot be issued for a bare IP). All module inputs
are documented in [`modules/team_vm/variables.tf`](../modules/team_vm/variables.tf).

To provision, from inside `courses/<course>/`:

1. Fill `users.csv` — one row per group, columns = member Technion emails
   (see `users.csv.example`).
2. Put the subscription id in `terraform.tfvars` (gitignored) — or pass it on
   the command line instead.
3. Run:

```bash
terraform init
terraform apply    # add -var="subscription_id=<id>" if not in terraform.tfvars
terraform output vm_fqdns                  # group → FQDN (derivable — see §5)
terraform output team_public_ip_addresses  # group → public IP (admin-side debugging)
```

You can now SSH any VM as admin **before any student key exists**:

```bash
ssh -i id_rsa_lab.pem vmadmin@<vm-fqdn>
```

---

## 3. Collect student public keys

Each group submits **one public key** plus their group id (`group01`, …) via
the shared spreadsheet (see the student doc §3.1 for what they run). Export the
sheet as CSV, then from inside `courses/<course>/` run:

```bash
python ../../ansible/scripts/parse_student_keys.py <exported.csv>
```

The parser ([`ansible/scripts/parse_student_keys.py`](../ansible/scripts/parse_student_keys.py))
validates each key, normalizes `group01` → `group_01` to match the Terraform
team names, and writes `keys/group_01.pub`, … into the course folder — exactly
where the deploy playbook (§4) looks for them. `keys/` is gitignored.

Sanity-check a received key if in doubt:

```bash
ssh-keygen -l -f keys/group01.pub      # prints fingerprint + type; errors if malformed
```

A valid line starts with `ssh-ed25519` (or `ssh-rsa`) — if it starts with
`-----BEGIN`, a group sent you a **private** key by mistake. Tell them to rotate
it and resend the `.pub`.

---

## 4. Push (and rotate / revoke) deploy keys in bulk (Ansible)

The playbook is
[`ansible/playbooks/deploy-keys.yml`](../ansible/playbooks/deploy-keys.yml): it
installs `keys/<group_name>.pub` as the **only** authorized key of the student
account `azureuser` on that group's VM (`exclusive: true`). It connects as
`vmadmin` using the Terraform-generated `inventory.ini` and `ansible.cfg` in
the course folder — never edit those by hand.

Run it from inside `courses/<course>/`:

```bash
ansible-playbook ../../ansible/playbooks/deploy-keys.yml                    # all groups
ansible-playbook -l <host> ../../ansible/playbooks/deploy-keys.yml         # one group
```

Because of `exclusive: true`, this playbook **is** your key-management interface:

| Task | What you do |
|------|-------------|
| Add a new group's key | drop `group_NN.pub` in `keys/` (or re-run the parser), re-run |
| **Rotate** a group's key | replace their `.pub`, re-run — old key stops working |
| **Revoke** a group | replace their `.pub` with an empty file, re-run |

(Adding a whole new *group* is a roster change: add the row to `users.csv` and
`terraform apply` first — that creates the VM and regenerates `inventory.ini`.)

Verify a group can no longer get in after revocation by checking the VM:

```bash
ssh -i id_rsa_lab.pem vmadmin@<vm-fqdn> 'sudo cat /home/azureuser/.ssh/authorized_keys'
```

---

## 5. Hand each group what they need

Nothing per-group needs to be distributed — none of it is secret, and the FQDN
is **derived from the group id**: the module sets the DNS label to
`<name_prefix>-<group id with - instead of _>`, so for this course
(`name_prefix = "sweng"`, `location = "eastus"`) group `group_02`'s address is
`sweng-group-02.eastus.cloudapp.azure.com`. The student doc states this formula
(§3.1), so each group derives their own FQDN; it is the address they use for
both HTTPS and SSH, and the domain they get a Let's Encrypt cert for.

> If a future course changes `name_prefix` or `location` in its `main.tf`,
> update the formula in the student doc to match.

The **public IPs** (`terraform output team_public_ip_addresses`) stay
admin-side — students never need them; you use them to separate DNS problems
from VM/NSG problems (FQDN fails but IP answers → DNS issue).

Announce once, to everyone:

- The FQDN formula above.
- The **deploy username** (`azureuser`).
- The open ports: **22** SSH (key-only), **80** ACME + redirect, **443** the
  app over HTTPS.

They store these in **their** GitHub repo — see student doc §3.1 and R6:

| What | Where in GitHub | Value |
|------|----------------|-------|
| `SSH_PRIVATE_KEY` | **Secret** | their `groupNN_deploy` private key |
| `SSH_HOST` | **Variable** | the VM's FQDN (not sensitive) |
| `SSH_USER` | **Variable** | `azureuser` (not sensitive) |

Remind groups: only the private key needs to be a *Secret* (masked in logs). The FQDN and username go in *Variables*.

---

## 6. Cost control — idle auto-deallocation (admin-managed)

Goal: when a VM has been idle for **T hours**, it **deallocates itself** so
compute billing stops. This is wired in by Terraform + cloud-init and runs as
**root** — it is **not** part of the students' repo or deploy flow, and students
are not meant to touch it (see the caveat at the end).

> **Why guest `poweroff` is not enough:** a shutdown from inside the guest leaves
> the VM in **"Stopped"**, which **still bills compute**. Only a control-plane
> **deallocate** reaches **"Stopped (deallocated)"** (no compute charge; you
> still pay for the managed disk and the static public IP). So the VM needs
> permission to call the Azure control plane on itself — that is what the
> managed identity below grants, narrowly.

### 6.1 Give each VM permission to deallocate *only itself*

A **system-assigned managed identity** + a **custom role** scoped to the single
VM. The identity can deallocate that one VM and read its state — nothing else.
Implemented in [`modules/team_vm/main.tf`](../modules/team_vm/main.tf)
(`azurerm_role_definition.self_deallocate` + the per-VM role assignment).

> A deallocated VM **cannot start itself** (it's off). The self-deallocate role
> deliberately omits `start`, so the in-guest watcher can never keep the VM
> running for free. Starting it back up is a separate decision — see §6.5.

### 6.2 The idle watcher (cloud-init, root-owned)

[`modules/team_vm/cloud-init.yaml`](../modules/team_vm/cloud-init.yaml) writes
a root-only script (`/opt/idlewatch/idlewatch.sh`) plus a systemd timer that
runs it every 15 minutes. When the 15-min CPU load average has stayed below
0.20 for `idle_shutdown_hours` (module variable, default **4 h**), the script
logs in with the managed identity and deallocates the VM via the Azure CLI.
Any activity resets the idle clock.

### 6.3 Why CPU load, not network traffic

The assignment requires an **external uptime monitor polling every ≤5 min**
(R9). Connection- or access-log-based idle detection would therefore **never**
see the VM as idle — the monitor's pings keep resetting the clock. **CPU load
average ignores those lightweight pings** (a health request costs ~no CPU), so
the VM still reads as idle and deallocates. Tune `LOAD_THRESHOLD` to your app's
resting load.

Expected side effect: once the VM deallocates, the external monitor will fire a
**DOWN alert**. That is normal for off-hours — tell groups to expect it, or set
a maintenance window in the monitor.

### 6.4 The daily backstop — built-in Auto-shutdown

In addition to the idle watcher, every VM gets Azure's built-in **Auto-shutdown**
(`azurerm_dev_test_global_vm_shutdown_schedule` in
[`modules/team_vm/main.tf`](../modules/team_vm/main.tf)). It deallocates on a
daily schedule set by the module's `auto_shutdown_time` variable (default
**23:50 UTC**; empty string disables it) and emails the first team member
30 minutes beforehand. It runs in the Azure control plane — time-based, not
idle-based, and it needs no managed identity.

### 6.5 Restarting a stopped VM — student portal access

A deallocated VM is off; it cannot be woken by traffic or SSH. Bringing it back
is a **control-plane** action, so it needs an Azure identity — separate from the
SSH PKI students use for day-to-day access (§3–§5).

Keep one narrow Azure capability for students: **starting their own VM**. Assign
each student (from `users.csv`) two built-in roles via their Technion (Entra)
account:

| Role | Scope | Purpose |
|------|-------|---------|
| `Reader` | the team **resource group** | see the VM in the portal |
| `Virtual Machine Contributor` | the team **VM** | start / stop / restart it |

With those, a student starts a stopped VM **in the browser portal** — Technion
login → the VM → **Start** (or `az vm start -n <vm> -g <rg>` if they happen to
have the CLI). No Azure CLI is required, no secret is handed out, and it's an
occasional action — so it doesn't reintroduce the SSO/tooling burden that made
plain SSH the daily path.

The VM's **own** managed identity (§6.1) still only gets `deallocate`, never
`start` — so the in-guest watcher can turn the VM off but can't keep it on.

### 6.6 On students reading the watcher

The watcher runs as **root** and isn't part of the students' repo, but it is
**not secret** — an inquisitive student can `sudo cat /opt/idlewatch/idlewatch.sh`
and read exactly how the deallocation works. That's fine, even desirable; it's a
good thing for them to learn from. Because `azureuser` has passwordless sudo, a
student *could* also stop the timer — so don't rely on the in-guest watcher
alone for the cost guarantee:

- Keep the **§6.4 Auto-shutdown** schedule as a staff-side backstop. It runs in
  the Azure control plane, which students have no access to, so it enforces a
  guaranteed daily deallocate regardless of what they do inside the guest.

Defense in depth: idle watcher for responsiveness (and as a teaching artifact),
Auto-shutdown as the floor.

---

## 7. Teardown

From inside `courses/<course>/`:

```bash
terraform destroy    # add -var="subscription_id=<id>" if not in terraform.tfvars
```

Destroys that course's VMs, NSGs, and public IPs in one shot (each course is a
separate state — other courses are untouched). Do this at the end of the term
to stop billing. Snapshot first if you want to keep any group's work.

---

## Notes & gotchas

- **Port 22 is open to the world.** GitHub-hosted runners have no fixed IP, so
  restricting SSH by source is not possible. Security is key-only
  (`PasswordAuthentication no`, enforced in cloud-init). The blast radius of a
  leaked deploy key is limited to one VM's `azureuser` account.
- **Don't put student keys on `vmadmin`.** Keep the blast radius small: a
  leaked deploy key touches one VM's `azureuser` account; your admin account
  stays untouched.
- **One source of truth.** `keys/` + `inventory.ini` + the playbook fully
  describe who has access. Never hand-edit `authorized_keys` on a VM — the next
  playbook run (`exclusive: true`) would wipe it.
