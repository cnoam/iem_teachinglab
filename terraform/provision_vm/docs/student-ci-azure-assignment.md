---
doc_kind : assignment
lifecycle : living
status : active
authority : source
scope : "Student assignment — CI/CD pipeline for a dockerized server, deployed to an Azure VM"
updated : 2026-07-05
---
# Assignment: CI/CD Pipeline for a Dockerized Server on Azure

## 1. Objective

Build an **automated CI/CD pipeline** that takes your dockerized server from a
`git push` all the way to a **running container on an Azure virtual machine**,
with no manual steps in between.

When you are done, pushing a commit to your `main` branch must:

1. Build and test your code,
2. Build a Docker image and push it to **GitHub Container Registry (GHCR)**,
3. Deploy and run that exact image on an **Azure VM**, and
4. Confirm the deployed server is healthy.

You will be evaluated on a **live demonstration**: you push a small visible
change, and the grader watches it reach the running Azure VM automatically.

---

## 2. Learning outcomes

By completing this assignment you will be able to:

- Containerize an application and run it reproducibly.
- Author a CI/CD pipeline using GitHub Actions.
- Publish and consume images from a container registry (GHCR).
- Deploy to a remote Linux host securely over SSH.
- Manage secrets so that **no credential ever appears in the repository or logs**.
- Verify a deployment automatically with a health check.

---

## 3. Assumptions & prerequisites

You are expected to already have, or to obtain:

- A **server application** of your own that runs in Docker (any language/stack).
  It must expose at least one **HTTP health endpoint** (e.g. `GET /health`
  returning HTTP 200).
- A **GitHub repository** that you own (public or private).

**The instructor provides the Azure VM.** You do **not** create, own, or pay for
any Azure resource — one Linux VM per group is provisioned for you. Its **FQDN**
follows directly from your group id (see §3.1) and is your deploy target for
the whole assignment.

You reach the VM over **plain SSH** as the `azureuser` user, with a key pair **you
generate yourself** — no extra tooling beyond `ssh`. The exact steps are in
§3.1; the same mechanism is what your CI uses to deploy.

To save cost, idle VMs are **automatically stopped**. You can **start your VM
yourself** from the **Azure portal** in a browser, using your Technion login
(portal → your VM → **Start**) — the instructor grants your account permission to
start and stop your own VM. You do **not** need the Azure CLI for this
assignment; the portal button is enough.

If your application needs a database or other dependency, run it as an
additional container via `docker compose` — the whole stack must come up
together.

### 3.1 VM access — sending your deploy key

The instructor provisions **one Azure VM per group**. Its **FQDN is derived
from your group id** — replace the underscore with a hyphen:

> `group_NN` → `sweng-group-NN.eastus.cloudapp.azure.com`

(e.g. `group_02` → `sweng-group-02.eastus.cloudapp.azure.com`). No one sends
you an address — derive it yourself.

The VM already has an `azureuser` account; you grant your pipeline access by
submitting your **public** key. You never receive a private key from the
instructor, and you never put a private key in the repository.

1. **Generate a dedicated deploy keypair** (do this once, per group, on a
   trusted machine — *not* your personal SSH key):
   ```bash
   ssh-keygen -t ed25519 -C "groupNN-deploy" -f groupNN_deploy -N ""
   ```
   Replace `NN` with your group number. This creates two files:
   - `groupNN_deploy` — **private key. Keep it secret. Never commit it.**
   - `groupNN_deploy.pub` — public key.

2. **Submit only the public key** — paste the one-line contents of
   `groupNN_deploy.pub` together with your group id (e.g. `group07`) into the
   shared spreadsheet the instructor provides. The instructor installs it on
   your VM's `azureuser` account.
   - If you ever paste something that starts with `-----BEGIN ... PRIVATE KEY`,
     **stop** — that is the private key, the wrong file. Paste the `.pub`
     contents only.

3. **Store the private key as a GitHub Actions secret**, and the host/user as
   Actions variables, in *your* repo (Settings → Secrets and variables → Actions):

   | Kind | Name | Value |
   |------|------|-------|
   | Secret | `SSH_PRIVATE_KEY` | the full contents of `groupNN_deploy` (private key, incl. header/footer) |
   | Variable | `SSH_HOST` | your VM's FQDN (derived from your group id, above) |
   | Variable | `SSH_USER` | `azureuser` |

   `SSH_PRIVATE_KEY` must be a **secret** (sensitive — never logged). `SSH_HOST`
   and `SSH_USER` are not sensitive and belong under the **Variables** tab, not
   Secrets — they don't need masking and variables are easier to inspect and edit.

   Your pipeline reads these at deploy time (R6). The private key must **never**
   appear in the repo, the image, or the logs.

4. **If your private key ever leaks** (committed, pasted in a log, shared):
   generate a new keypair, submit the new `.pub` (and tell the instructor so
   the old key is revoked), update `SSH_PRIVATE_KEY`. Document that you rotated
   it in your report.

> Connectivity reminder: the VM accepts **22** (deploy/SSH, key-only — no
> passwords), **80** (Let's Encrypt validation + HTTP→HTTPS redirect), and
> **443** (your app over HTTPS). Your **FQDN** (derived above) — not an IP — is
> your public HTTPS address (see R10). Design your deployment around those ports.

---

## 4. Functional requirements

Each requirement is **mandatory** unless marked *(optional)*. Number them in
your report so the grader can map your work to this list.

### R1 — Source control & trigger
- R1.1 All source, the `Dockerfile`/`docker-compose.yml`, and the pipeline
  definition live in **one Git repository**.
- R1.2 The pipeline runs **automatically** on every push to the `main` branch.
- R1.3 The pipeline also runs on **pull requests** to `main`, but a PR run must
  **stop after the test stage** — it must **not** deploy.

### R2 — Build & test stage
- R2.1 The pipeline installs dependencies and **runs your automated tests**.
- R2.2 If tests fail, the pipeline **fails and does not proceed** to build,
  push, or deploy.
- R2.3 The project must contain at least a **minimal test** that actually
  exercises your code (a placeholder that always passes is not acceptable).

### R3 — Container image build
- R3.1 The pipeline builds a Docker image from your `Dockerfile`.
- R3.2 The image is tagged with **both**:
  - a stable tag `latest`, **and**
  - an **immutable tag** derived from the commit (the short git SHA).
- R3.3 The build must be **reproducible from the repository alone** — no files
  copied in by hand on the runner.

### R4 — Push to registry (GHCR)
- R4.1 The image is pushed to **GitHub Container Registry**
  (`ghcr.io/<owner>/<image>`).
- R4.2 Authentication to GHCR uses the **built-in `GITHUB_TOKEN`** or a
  dedicated token — **never** a hard-coded credential.
- R4.3 Both tags from R3.2 are pushed.

> **No separate signup needed.** GHCR is part of every GitHub account. The
> built-in `GITHUB_TOKEN` authenticates your pipeline automatically — no token
> creation or registry registration is required.

### R5 — Deploy to the Azure VM
- R5.1 After a successful push to `main`, the pipeline connects to the Azure VM
  over **SSH** and deploys the new image.
- R5.2 The VM **pulls the image from GHCR** and runs it (e.g. via
  `docker compose pull && docker compose up -d`). The VM must **not** build the
  image locally.
- R5.3 The deploy must be **repeatable**: running the pipeline twice on the same
  commit leaves the server in the same correct state (idempotent).
- R5.4 The deployed container must **survive a VM reboot** (use a restart policy
  such as `restart: unless-stopped`).

### R6 — Secrets management
- R6.1 All secrets (SSH private key, host address, any app secrets) are stored
  as **GitHub Actions secrets**, injected at runtime.
- R6.2 **No secret may appear** in the repository, in the image, or in the
  pipeline logs.
- R6.3 The VM must **not** permit password SSH login for the deploy account —
  **key-based authentication only**. This is enforced by the instructor at
  provisioning time (via cloud-init). You do not need to configure it; the
  grader will verify it is in effect.

### R7 — Post-deploy verification
- R7.1 After deploying, the pipeline calls the server's **health endpoint** and
  **fails the run if the server is not healthy** within a reasonable timeout.
- R7.2 The health check must hit the **actually deployed** server (the Azure VM),
  not a local container on the runner.

> **Implementation hint:** a single `curl` call is enough:
> ```bash
> curl --fail --retry 10 --retry-delay 5 --retry-connrefused \
>   https://<fqdn>/health
> ```
> `--fail` makes curl exit non-zero on any HTTP error status; `--retry` retries
> on transient failures and handles container startup delay. No explicit `sleep`
> step is needed.

### R8 — Failure behaviour
- R8.1 A failure in any stage must make the **whole pipeline run fail**
  (red/❌ in GitHub), never a silent pass.
- R8.2 *(optional)* On a failed health check, automatically **roll back** to the
  previously deployed image.

### R9 — External health monitoring
- R9.1 Configure an **external uptime-monitoring service** (e.g.
  [UptimeRobot](https://uptimerobot.com), Better Stack, Healthchecks.io, or
  equivalent) that polls your server's **public health endpoint** at a regular
  interval (≤ 5 min).
- R9.2 The monitor must be **independent of your VM** — a third-party service or
  a host other than the server it watches. A check that runs *on* the VM does
  not count (it can't detect the VM being down).
- R9.3 The monitor must **alert** you (email/Slack/etc.) when the server is down,
  and recover (resolve) when it comes back.
- R9.4 You must be able to **show the monitor's status page / history** at the
  demo, including at least one down→up transition (trigger one by stopping the
  container briefly).

### R10 — Valid public HTTPS
- R10.1 The server must be reachable over **HTTPS at a real, resolvable domain
  name** — the Azure-provided FQDN for your VM
  (`<label>.<region>.cloudapp.azure.com`) or your own domain. **A bare IP
  address is not acceptable** (browsers and Let's Encrypt both reject it).
- R10.2 The TLS certificate must be issued by **Let's Encrypt** — **not
  self-signed**. `curl https://<your-fqdn>/`
  must succeed **without** `-k`/`--insecure`, and a browser must show a valid
  padlock with no warning.
- R10.3 Certificate **renewal must be automated** (e.g. certbot timer / the proxy
  handles it). A manually renewed cert that will silently expire is not
  acceptable.
- R10.4 Plain HTTP must either be **unavailable or redirect to HTTPS** — the app
  is served only over TLS.
- R10.5 All earlier requirements that reach "the server" (R5 deploy, R7 health
  check, R9 monitor) must target this **HTTPS FQDN**.

> **Heads-up on ports & DNS:** Let's Encrypt must reach your server to validate
> the domain. The **HTTP-01** challenge needs **inbound port 80**; the
> **TLS-ALPN-01** challenge works over **port 443**; **DNS-01** needs no inbound
> port but requires DNS-provider API access. Your VM exposes **22, 80, and 443**,
> so the standard **HTTP-01** flow works out of the box. The DNS label is already
> set on your VM, giving the **FQDN you derived in §3.1**
> (`sweng-group-NN.eastus.cloudapp.azure.com`) — use that as your HTTPS address
> (a certificate cannot be issued for a raw IP).
>
> **A reverse proxy is *not* required.** R10 cares only about the result — valid,
> auto-renewing HTTPS at your FQDN — not how you get there. Pick whichever of
> these fits your stack:
>
> - **App terminates TLS itself.** Obtain the cert with `certbot` (standalone or
>   webroot on port 80), point your server at the cert/key files, and have it
>   listen on 443. Automate renewal with a `certbot renew` timer plus a deploy
>   hook that reloads/restarts your container. Some frameworks/libraries can do
>   ACME themselves (e.g. Go's `autocert`) — then the app handles issuance and
>   renewal with no extra tool.
> - **A TLS-terminating proxy** (optional convenience). [Caddy](https://caddyserver.com)
>   is the lowest-effort: a two-line `Caddyfile` obtains, installs, renews the
>   cert, and redirects HTTP→HTTPS automatically. `certbot + nginx` works too.
>   Since you are already using docker-compose, the simplest approach is to add
>   a `caddy` service to your `docker-compose.yml` — Caddy then sits in front of
>   your app container and handles everything automatically.
>
> Whatever you choose, **renewal must be automatic** (R10.3) and HTTP must be
> unavailable or redirect to HTTPS (R10.4).
>
> **Using gunicorn (or a similar app server)?** Gunicorn is fine as your *app
> server*, but do **not** expose it to the internet with TLS directly: its own
> docs advise against it (sync workers are vulnerable to slow-client/Slowloris
> attacks, and a renewed cert needs a restart to load). The standard pattern is
> to run gunicorn on a plain internal HTTP port and put a thin TLS terminator
> (**Caddy** or **nginx**) in front to handle HTTPS, Let's Encrypt, and the
> HTTP→HTTPS redirect. For gunicorn specifically, that fronting proxy is the
> recommended setup, not just a convenience.

---

## 5. Constraints & rules

- **One target VM.** Deploy to a single Azure VM; clustering/orchestration
  (AKS, Kubernetes) is out of scope.
- **No manual deploy steps.** Once you push to `main`, you may not touch the VM
  by hand for the deployment to complete. SSHing in to *inspect* is allowed;
  SSHing in to *finish the deploy* is not.
- **No secrets in git, ever.** A single committed credential (key, password,
  token) fails the assignment. If you leak one, **rotate it** and document that
  you did.
- **The pipeline is the source of truth.** The grader reads your pipeline file
  to understand your deployment; it must match what actually happens.
- **The VM exposes ports 22, 80, and 443 only** — the instructor has configured
  this. Do not expect to open additional ports.

---

## 6. Deliverables

Submit the following:

1. **Repository URL** with:
   - Application source + tests,
   - `Dockerfile` and `docker-compose.yml`,
   - The pipeline definition (e.g. `.github/workflows/ci.yml`).
2. **`README.md`** containing:
   - A one-paragraph description of the app and its health endpoint,
   - A **diagram or numbered description** of the pipeline stages
     (push → test → build → push image → deploy → verify),
   - The **list of GitHub secrets** you use and what each is for
     (names only — never values),
   - How you provisioned the Azure VM (steps or script).
3. **A short report (`REPORT.md`, ~1–2 pages)** mapping each requirement
   **R1–R8** to where/how you satisfied it, and noting anything you left
   incomplete.
4. **Evidence**: a link to at least one **successful pipeline run** and one
   **failing run** (e.g. a PR where a test failed and the deploy was blocked).

---

## 7. Acceptance criteria (how it will be checked)

Your submission is accepted when **all** of the following are demonstrated live:

1. **A:** You make a small, visible change (e.g. change a string returned by an
   endpoint), commit, and push to `main`.
2. **B:** The pipeline starts automatically and runs test → build → push →
   deploy without any manual intervention.
3. **C:** The new image appears in GHCR tagged with the commit SHA.
4. **D:** Within a few minutes, the **Azure VM serves the changed response**
   over its **HTTPS FQDN** (the grader runs `curl https://<your-fqdn>/...`
   **without** `-k` and sees your change, with a valid certificate).
5. **E:** The pipeline's **health check passed** as part of the run.
6. **F:** You open a PR that **breaks a test**; the grader confirms the pipeline
   **fails and does not deploy**.
7. **G:** The grader inspects logs and repo and finds **no exposed secrets**, and
   confirms SSH password login on the VM is disabled.
8. **H:** You show the **external uptime monitor** (R9): its status page, the
   ≤ 5 min polling interval, and at least one **down→up** event with an alert.
9. **I:** The certificate is **publicly trusted and auto-renewing** (R10): a
   browser shows a valid padlock, and `openssl s_client`/`curl` confirm a
   Let's Encrypt cert; plain HTTP is unavailable or redirects to HTTPS.

Any of B, D, E, F, G, H, or I failing means the assignment is **not yet
accepted**; fix and re-demo.

---

## 8. Suggested milestones (not graded, just a sane order)

1. App runs locally in Docker with a working health endpoint.
2. Pipeline builds + tests on every push (no deploy yet).
3. Pipeline pushes the image to GHCR.
4. SSH into your VM and verify you can manually run `docker compose pull && docker compose up -d` before wiring up the pipeline. (The VM was provisioned by the instructor.)
5. Pipeline deploys to the VM over SSH using secrets.
6. Obtain a Let's Encrypt cert for your VM's FQDN (the instructor already set
   the DNS label); serve over HTTPS (R10).
7. Pipeline adds the post-deploy health check (against the HTTPS FQDN) and
   proper failure handling.
8. Set up the external uptime monitor + alert (R9).
9. Polish: SHA tagging, PR-blocks-deploy, README + report.

---

## 9. Stretch goals *(optional, for the curious)*

- **If you have your own Azure subscription**, reproduce the VM provisioning with
  Terraform or Bicep (the instructor already does this — this goal means doing
  it yourself for a separate instance).
- **Automatic rollback** on a failed health check (R8.2).
- **Zero-downtime deploy** (start the new container before stopping the old).
- **Separate `staging` and `production`** environments triggered by different
  branches or manual approval.
- **Build caching** to speed up image builds.

---

## 10. A note on safety

This pipeline can reach a live server. Before you wire up automatic deploys:

- Use a **dedicated deploy SSH key** for the VM, not your personal key.
- Do not expose extra ports from inside Docker (e.g. avoid `-p 8080:8080` for ports that should stay internal).
- Treat every token as if it will leak — store them only as GitHub secrets, and
  know how to **rotate** each one.
