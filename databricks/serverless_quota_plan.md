# Adapting the usage-quota monitor to serverless compute

Status: plan / not yet implemented.
Written 2026-09-16. Supersedes the "no equivalent uptime-monitor hook" paragraph in
`terraform/dbr-serverless/MIGRATION.md`.

Goal: keep enforcing a cumulative daily compute quota per student group, now that
`terraform/dbr-serverless/` deploys no per-group clusters. Both deployments must stay
operational: `dbr/` (classic clusters, today's code path) and `dbr-serverless/` (new path).

**Confirmed by live test (2026-09-16, see 2.5): removing a student's group entitlement does
not stop an already-running pure-Python notebook command** — a heartbeat loop kept running
untouched throughout a ~4.5-minute block window, while new commands and page loads were
blocked immediately. Whether an in-flight *Spark* query survives the same block is untested
and not the same claim — Spark Connect queries run through a control-plane-authorized path,
and that path was observed breaking during the block (new commands failed against it), so a
running Spark query may behave differently. What's certain either way: no documented API can
cancel a notebook-sourced query at all (see 2.5), and the execution timeout only bounds Spark
Connect queries, not general compute. So "enforce" in this plan means *prevent new work* for
the case actually tested (pure-Python), and *at best* the same for Spark — never assume
"terminate active work" without a further test. Read this before the rest of the doc.

---

## 1. Fact-check of the Gemini proposal

Checked against the live `94290_2026` workspace (read-only API calls) and current Azure
Databricks docs. Summary: the *shape* of the proposal is right (aggregate centrally, kill
and block per workload type), but most of the specific mechanisms are wrong.

| Gemini claim | Verdict | Evidence |
|---|---|---|
| Query `system.query.history` and filter `compute.is_serverless = TRUE` | **Wrong column.** The struct is `compute.{type, cluster_id, warehouse_id}`; `type` is `WAREHOUSE` or `SERVERLESS_COMPUTE`. `is_serverless` exists, but in `system.billing.usage` (`product_features.is_serverless`) — two different tables conflated. | query-history system table reference |
| Use that table for enforcement | **Unusable for enforcement.** Records are "typically available within one hour"; table is Public Preview. A quota that reacts an hour late is not a quota. | same doc, "Record availability" |
| — (not proposed) | **The Query History *API* is the right source.** `GET /api/2.0/sql/history/queries` is real-time and, verified live, returns serverless-notebook statements: `client_application: "Databricks Notebooks"`, `warehouse_id: "0000000000000000"`, `query_source.notebook_id`, plus `user_name`, `duration`, `status`, `is_cancelable`. Filtering `statuses: [RUNNING, QUEUED]` is accepted, so in-flight statements are visible too. | live probe against 94290_2026 |
| Jobs API `2.1` for `runs/list` / `runs/cancel` | **Stale version.** `2.2` is current and works on this workspace. Also near-moot here: `dbr-serverless/` creates no jobs, and students have none. | live probe returned `{}` for active runs |
| Stop the serverless SQL warehouse; keep it stopped to block queries | **Two errors.** (a) The deployed `Shared Student Warehouse` has `enable_serverless_compute: false` — it is a classic PRO warehouse, so it is not serverless usage at all. (b) A stopped warehouse auto-starts on the next query, so "keep it stopped" blocks nothing. (c) The warehouse is shared by all groups, so stopping it punishes everyone. | live `/api/2.0/sql/warehouses` |
| Revoke `CAN_USE` on the warehouse to block a group | **Wrong layer, and hazardous.** Warehouse permissions are TF-managed and `databricks_permissions` is authoritative — hand-editing them fights Terraform. | `modules/unified_catalog_setup/main.tf` |
| Pause scheduled jobs via `jobs/update` | Correct API, but nothing to pause in this deployment. | — |
| Native budgets can cap the spend | **Not for serverless compute.** Budget "Block usage" enforcement exists only for Unity Gateway (AI) endpoints; serverless compute budgets are alert-only, account-admin scoped, with up to 24h notification delay. | budgets doc, "Known limitations" |
| Watchdog thread with `os._exit(1)` in notebooks | **Reject.** It lives in student-editable code; it is a suggestion, not enforcement. | — |
| `spark.databricks.execution.timeout` | **Keep, with a correction — and narrower than it sounds.** The workspace-level *Serverless interactive execution timeout* (Settings > Compute, default 2.5 h) is the enforceable one and is already documented in `MIGRATION.md`; the spark property is the per-notebook/per-job override. But the docs state it is "the execution timeout, in seconds, **for Spark Connect queries**" — it only bounds Spark Connect queries, nothing else. **Confirmed empirically by the operator:** a pure-Python infinite loop with no Spark calls, run after setting this timeout, was NOT killed. It is not a general compute watchdog. | [spark/conf#serverless](https://learn.microsoft.com/en-us/azure/databricks/spark/conf#configure-spark-properties-for-serverless-notebooks-and-jobs), [serverless overspend protection](https://learn.microsoft.com/en-us/azure/databricks/compute/serverless/notebooks#serverless-overspend-protection), operator test 2026-09-16 |

### 1a. Residual gap: pure-Python runaway compute has no real-time backstop

**This is a capability regression versus `dbr/`, not just a design limitation, and it needs
to be stated to the course, not buried in this doc.**

On classic clusters, a buggy or runaway pure-Python loop was still bounded: `poll_clusters.py`
measures raw cluster wall-clock uptime regardless of what code the cluster is running, and
terminates the cluster at `DATABRICKS_MAX_UPTIME` no matter what it's doing. On serverless,
confirmed empirically (operator test, 2026-09-16: execution timeout set, pure-Python infinite
loop run, not killed) and by docs (`spark.databricks.execution.timeout` bounds only "Spark
Connect queries"): a pure-Python cell with no Spark calls is invisible to *both* of the two
real-time mechanisms this plan otherwise relies on —

- the workspace **execution timeout**, because it only watches Spark Connect queries, and
- the **Query History API**, because a cell that calls no Spark API issues no query and
  therefore no query-history record — this plan's whole enforcement/collection mechanism.

Such a loop is also not "idle" in the sense the undocumented idle-detach timer presumably
means (it's actively consuming CPU), so there is no reason to expect that mechanism catches
it either, though its behavior is undocumented enough that this can't be ruled out.

**Consequence: nothing in real time stops a pure-Python runaway loop on serverless.** The
only signal that eventually sees it is `system.billing.usage` (hours-delayed). This plan
therefore treats `system.billing.usage` polling as more than a calibration nicety — it's
promoted to a coarse, hours-late **backstop enforcement layer** specifically for this gap
(see 2.6a). Recommend flagging this explicitly to whoever owns the course: the tolerance for
"a runaway loop burns compute for a few hours before anyone notices" is a policy call, not an
engineering one.

### The consequence that reshapes the design

The old quota measured **cluster wall-clock uptime**. Serverless billing turns out to work
the same way — confirmed against docs and a Databricks-staff community answer: serverless
notebook/job usage is metered by **cumulative attached session time**
(`system.billing.usage` records start/end timestamps per metering period, DBUs, notebook/job
id), not by SQL/Spark execution duration. There is an idle-termination mechanism that
eventually detaches an unused session ("idle termination of serverless compute can cause you
to lose in-progress work"), but **no documented or configurable duration exists** — a
Databricks employee said as much on the community forum — and no API exposes current session
state or its idle timer.

So the Query History API's `duration` is a real-time *proxy*, not the billed quantity itself,
and the gap runs in a specific direction:

- A pure-Python cell (`while True: pass`, `time.sleep`) issues no statement and is
  invisible to query history — **confirmed, see 1a**, not merely expected.
- Time spent idle-but-attached between commands (typing, reading output, thinking) **is
  billed but is not query-execution time**, so it is invisible to this quota and will always
  undercount true cost. There is no way to close this gap in real time — no API lists active
  serverless sessions or their attach/idle state.

So the honest scope of the new feature is: *we enforce a daily quota on SQL/Spark execution
time per group, as a proxy for compute cost, known to undercount idle-attached time.*
`system.billing.usage` (`identity_metadata.run_as`, `product_features.is_serverless`,
`billing_origin_product IN ('INTERACTIVE','JOBS')`) is the accurate source, but it updates
every few hours, so it's a *reconciliation/calibration* input for the daily report — compare
enforced-proxy minutes against actual billed minutes per group, and use the gap to recalibrate
thresholds over time — not an enforcement source.

Do not write documentation or emails that imply uptime-equivalent or billing-equivalent
coverage; say "execution time," not "usage" or "uptime."

---

## 2. Design

### 2.1 Pluggable backend, classic path untouched

```
databricks/resource_manager/
    backends/base.py        UsageBackend ABC: collect() / enforce() / restore() / report(day)
    backends/classic.py     thin wrapper over today's cluster code — behavior unchanged
    backends/serverless.py  new
    serverless_usage.py     query-history ingest
    group_map.py            email -> group_NN resolution
```

`poll_clusters.py` and `end_of_day_operations.py` stay as the cron entry points and become
thin dispatchers on `QUOTA_MODE` (`classic` | `serverless`, default `classic`). Deployments
that set nothing keep today's behavior exactly.

New code uses the `databricks-sdk` package. Do **not** extend `DataBricksClusterOps` /
`DataBricksGroups` — they sit on the deprecated `databricks_cli` package.

### 2.2 Ingest: idempotent, keyed by `query_id`

Do **not** port `update_cumulative_uptime`'s delta-bookmark logic. That design exists
because clusters expose only a current state, not events. Queries *are* events with stable
ids, so:

1. Poll `GET /api/2.0/sql/history/queries` with
   `filter_by.query_start_time_range.start_time_ms = watermark - 15 min` (slack for
   late-arriving records), following `next_page_token`.
2. Upsert each record by `query_id` (`replace`, so a RUNNING record is later overwritten by
   its FINISHED version and never double-counted).
3. Include `RUNNING`/`QUEUED` records so a single long statement counts against the quota
   while it is still running. **Live-tested correction:** `duration` is `null` on RUNNING
   rows — it only populates once a statement reaches a terminal state (confirmed: a ~48s
   query showed `duration: null` on every poll while `status: RUNNING`, then `duration: 47903`
   once `FINISHED`). `query_start_time_ms`, however, *is* present on RUNNING rows. For any
   row still RUNNING/QUEUED at ingest time, compute `elapsed_ms = now_ms - query_start_time_ms`
   instead of reading `duration`; re-derive it fresh on every poll rather than trusting a
   cached value, since the row will keep updating until it goes final. Validated against a
   real query: the live-computed estimate ran a few seconds ahead of the eventual final
   `duration` (plausibly counting queue/compile time) — conservative in the right direction
   for a quota, not a bug to fix.
4. Group usage for the day = aggregate of `duration` (terminal rows) or the computed
   `elapsed_ms` (still-running rows) over rows for that group's members (see 2.3a for SUM vs.
   union).

**Warehouse queries count too.** No serverless-only filter is applied: statements run on
the shared PRO warehouse are real billable compute and belong in the same quota, even
though section 1 establishes that warehouse is not *serverless*. This is deliberate, and it
is also the robust choice — the API's only serverless marker is the all-zeros
`warehouse_id`/`endpoint_id` sentinel, which is undocumented and could change.

This is immune to the double-count and midnight-reset bugs the delta code was written to dodge.

### 2.3 Attribution: user -> group

The API keys on `user_name` (email). Map email -> `group_NN` from workspace group
membership (`group_NN` -> members), cached per run. Terraform's `group_configs` is the
source of truth for which groups exist. Unmapped users (staff, SPs) go to a
`__ungrouped__` bucket that is reported but never blocked.

### 2.3a Aggregation semantics: SUM vs. union — decided (union)

One cluster had one clock: four group members attached to `cluster_07` burned one minute of
quota per minute, regardless of how many were working. Query duration does not behave that
way. `SUM(duration)` over a 4-member group means four students running concurrently spend
quota at 4x wall-clock.

Two options:

- **SUM of durations** — penalizes collaboration (4 members running concurrently = 4x);
  and, per the billing-model correction above, does *not* actually track cost any better
  than union does, since neither captures idle-attached time.
- **Union of execution intervals** — wall-clock time during which *any* member of the group
  was executing something. Closer to the old per-cluster semantics and to what students
  expect from "your group gets N minutes a day".

**Decided: union** (operator confirmed) — it matches the old per-cluster semantics, keeps
the old thresholds roughly interpretable, and doesn't penalize a group for working together.
Computable from the same rows (`start_time_ms`, `start_time_ms + duration`) with an
interval-merge. State this in the warning email so students can reason about it
("group execution time," not "per-student time").

**Interaction with 2.2's RUNNING-row handling — must compute at check time, never store an
accumulated total.** A terminal row's interval is `[query_start_time_ms, query_start_time_ms +
duration]`, fixed. A still-RUNNING row's interval is `[query_start_time_ms, now_ms]` — its
end keeps moving, so the same row's contribution to the union changes on every poll even with
no new student activity. That's correct and fine for a live threshold check (recompute the
merge fresh from `QueryUsage` rows on every poll), but it means the quota check must always
read raw rows and merge live — never persist a running `used_seconds` counter for the
in-progress day. `GroupDailyUsage` (2.4) is the only accumulated total, and it's written once
at end-of-day rollup, by which point every row for that day is terminal. Getting this
backwards (incrementally accumulating union "so far" into a counter) reintroduces exactly the
double-count risk that keying ingest by `query_id` was meant to avoid.

### 2.4 New tables (additive only)

The production sqlite file has live data and `CLUSTER_UPTIMES_DB` is load-bearing in both
cron wrapper scripts. Add tables; do not rename or alter `cluster_uptimes`,
`cluster_cumulative_uptimes`, `clusterinfo`.

- `QueryUsage(query_id PK, user_name, group_name, day, duration_ms, start_time_ms, status)`
  - `day` is the **local date** (the quota-checker server's TZ is already set to
    Asia/Jerusalem, per the operator), derived from the API's epoch-UTC `query_start_time_ms`
    via `datetime.fromtimestamp(ms/1000).date()` at ingest — the same implicit local-time
    behavior the classic code already relies on (`date.today()`, `datetime.now()`). This
    matches the 00:05 local cron reset and the "quota resets at midnight" text in student
    emails; UTC bucketing would desync those by Jerusalem's UTC+2/+3 offset. Store
    `start_time_ms` raw regardless, so the bucketing can be recomputed if ever needed.
- `GroupQuotaState(group_name, day, warned BOOL, blocked BOOL, blocked_at)`
- `GroupDailyUsage(group_name, date, used_seconds)` — history, mirrors the classic rollup
- `IngestWatermark(backend PK, last_seen_ms)`

### 2.5 Enforcement lever — confirmed: blocks new work, does not touch running work

**Live test, 2026-09-16, `94290_2026`, test user `efratsupp@technion.ac.il` (member of
`group_01`), with the operator's consent to test freely against that workspace:**

1. `efratsupp` started a pure-Python heartbeat loop (`time.sleep(2)` + print, no Spark calls)
   in a notebook attached to Serverless.
2. While it was running, `group_01` was removed from `all_student_groups` via SCIM PATCH
   (`10:52:56 +03:00`).
3. **The already-running loop was completely unaffected — it kept printing heartbeats for
   the entire ~4.5-minute block window**, confirmed both live and by inspecting the output
   timestamps after restore.
4. **New work was blocked immediately**, at two levels: running a *new* cell in the same
   notebook failed (`Unexpected token '<', "<!doctype "... is not valid JSON` — the frontend
   hit an HTML error/redirect page instead of a JSON API response); reloading the notebook
   page outright failed with `You do not have permission to access this page in workspace
   <id>`.
5. `group_01` was restored (`10:57:38 +03:00`). Access was confirmed back on the operator's
   next reload, at an unmeasured point after restore — **not** confirmed sub-second or
   "immediate"; both the block-taking-effect time and the restore-taking-effect time are
   bounded only by "within the ~4.5-minute window / by next reload," not measured precisely.
   If actual propagation turns out to be minutes rather than seconds, a student gets that
   many extra minutes of new-work dispatch after a threshold trips — relevant to picking the
   poll cadence in 2.5's "re-assert every poll" design; don't assume it's fast without
   measuring.

**Conclusion, scoped to what was tested:** removing the group is a **prevent-new-work**
lever for the pure-Python case — it blocked new command dispatch and all page access, while
the already-running loop kept going untouched for the whole window. It does **not**
terminate a pure-Python command already in flight. Whether it terminates an in-flight *Spark*
query is untested (see the callout above) — plausible either way, since the control-plane
path that Spark Connect queries run through was observed breaking for new work during the
block. Combined with 1a (no real-time detection for pure-Python compute) and the earlier
finding that no cancel API exists for notebook-sourced queries: **for pure-Python compute,
nothing in this design, or apparently available at all, can forcibly stop an in-flight
command.** For Spark-based compute, the same is true unless a further test shows otherwise.
Either way, the only thing "enforcement" can *reliably* do is stop the *next* command.

This at minimum narrows, and for the pure-Python case contradicts outright, the "automatically
terminating active sessions" framing in Gemini's original goal statement.

Per group, at poll time:

- **soft threshold** -> warning email (reuse `resource_manager/user_mail.send_emails`), once per day.
- **hard threshold** -> block *new* work: remove `group_NN` from `all_student_groups` via
  SCIM PATCH. That group is the isolation boundary — it carries `workspace-access`,
  `databricks-sql-access`, warehouse `CAN_USE` and the catalog grants (verified live) — so
  removing the child group drops all of them at once, per group, reversibly, and — per the
  test above — quickly.
  This cut point is structural, not lucky: `main.tf` creates every
  `databricks_user.workspace_user` with `workspace_access = false`, so students hold the
  entitlement *only* by inheritance through `all_student_groups`. Cutting that edge is the
  only place where a single, reversible, per-group operation removes workspace access.
  **Whatever the group was already running when blocked keeps running to completion,
  unaffected — plan and communicate around this, don't assume the block is a stop.**
- **in-flight job runs** -> `POST /api/2.2/jobs/runs/cancel` for runs attributable to the
  group. Untested live (no jobs exist in this deployment) but documented and, unlike the
  notebook case, a real termination API — moot for `dbr-serverless/` today, kept for
  completeness / future jobs use.
- **in-flight notebook statements/sessions** -> **no API exists, and now empirically
  confirmed unreachable even via the entitlement-removal side door.** The workspace
  interactive execution timeout is the only backstop, and it only covers Spark Connect
  queries (1a). Say so plainly in the runbook: *there is no way to stop a student's
  already-running notebook code once quota is exceeded.*

Re-assert the block on every poll, so it stays self-healing for *new* attempts even though it
can't touch what's already running.

**Terraform interaction (pitfall):** `databricks_group_member.all_students_group_assignment`
manages exactly this membership. A mid-day `terraform apply` silently lifts an active block.
Same class as the "`databricks_permissions` is authoritative" pitfall already in
`terraform/dbr/CLAUDE.md`. Mitigations: re-assert each poll, and document "don't apply
mid-day; if you do, the next poll restores the block within the poll interval."

### 2.6 Daily reset

`end_of_day_operations.py` in serverless mode: re-add every blocked `group_NN` to
`all_student_groups`, roll `QueryUsage` up into `GroupDailyUsage`, clear `GroupQuotaState`,
purge `QueryUsage` rows older than the retention window, email the daily report.

### 2.6a Billing-usage poll — reconciliation *and* the only backstop for 1a

`system.billing.usage` for the target day is typically available within a few hours, not
overnight-only — poll it periodically during the day (e.g. every 30-60 min, same cadence
class as the quota poller), not just once at end-of-day. Two jobs, one query:

1. **Reconciliation (soft).** Join by `identity_metadata.run_as` -> group, add actual billed
   minutes per group to the daily report alongside the enforced proxy minutes. Surfaces the
   known undercount (idle-attached time, and per 1a, pure-Python compute) and gives the
   operator real data to recalibrate thresholds instead of guessing.
2. **Backstop enforcement (required, see step 5).** If a group's billed minutes for the day
   exceed a separate, more generous backstop threshold — sized for "this can only mean a
   runaway process, not normal use" — apply the same block as the primary quota (2.5), even
   though the primary (query-history-based) usage for that group looks fine. This is the only
   mechanism in the whole design that catches 1a; it is hours-late by nature (`system.billing.usage`
   latency), so it is not a substitute for the query-history-based quota, only a supplement to
   it. And per 2.5's live-confirmed limitation: this block, like the primary one, only
   prevents *new* work — if the runaway loop from 1a is still the thing executing, this
   backstop cannot stop it either. It bounds how much *additional* damage accrues after
   detection, not the damage already in flight when detected.

Skip both silently (log, don't crash) if the account lacks read access to
`system.billing.usage` — but flag this loudly in the daily report if so, since it means the
1a gap is completely uncovered, not just delayed.

---

## 3. Rollout

**Step 0 — done.** Both open questions resolved by live test against `94290_2026`,
2026-09-16 (operator confirmed this workspace is free to test against): the pure-Python
invisibility question (1a) and the enforcement-lever behavior (2.5). Neither needs re-testing.

**Step 1** — refactor to the `UsageBackend` interface; classic backend wraps existing code;
existing tests stay green. No behavior change, deployable on its own.

**Step 2** — serverless collector + reporting only. No emails, no blocking. Run it alongside
the real course for a week and compare its numbers against `system.billing.usage`.

**Step 3** — enable warning emails.

**Step 4** — enable blocking. The lever is confirmed working as a **prevent-new-work**
control for pure-Python compute (2.5) — reliable, and in effect somewhere within the
~4.5-minute test window (not measured precisely; do a timed test before relying on a specific
poll cadence to bound exposure). Before enabling, make sure the warning email and any
operator-facing docs say "you will be blocked from *starting new* work," not "your session
will be stopped" — the latter is verified false for pure-Python work and unverified either
way for Spark work.

**Step 5** — enable the `system.billing.usage` backstop poll (2.6a), once step 4 is stable.
This is the only thing standing between a pure-Python runaway loop and a few hours of
unbounded compute (1a) — treat it as required, not optional, before calling the migration
done. Remember it inherits the same limitation as step 4: it can only prevent *further*
new work once it fires, not stop what's already running.

## 4. Tests

`tests/` + `pytest.ini` already exist. Add recorded query-history JSON fixtures (a
serverless-notebook record, a warehouse record, a RUNNING record, a paginated response) so
the whole serverless path is testable with no workspace. Cover: idempotent re-ingest of the
same `query_id`, RUNNING-then-FINISHED replacement, watermark slack, group attribution of an
unknown email.

## 5. Decisions already made by the operator

- **Day bucketing: local time** (server TZ is Jerusalem) — see 2.4.
- **Aggregation: union-of-intervals**, not SUM-of-durations — see 2.3a.
- **Billing model: confirmed cumulative attached session time**, not per-query duration —
  see section 1. No documented/configurable idle-detach timeout exists.
- **Enforcement lever confirmed (live test, 2026-09-16) for pure-Python compute: group
  removal blocks new work (new commands, new page loads) reliably, at an unmeasured but
  bounded latency, but does not terminate work already running.** Not established for
  in-flight Spark queries — see 2.5. No fallback lever needed; SCIM `active=false` was never
  tried because it would not have changed this conclusion (same class of "revoke entitlement"
  mechanism).
- **`duration` on RUNNING query-history rows is `null`; use `query_start_time_ms` to compute
  elapsed time instead** — live-tested and confirmed, see 2.2.
- **Quota unit: per group** (operator confirmed) — matches the old per-cluster quota, and the
  only available block lever is per-group anyway (workspace access is inherited via group
  membership, not held individually — see 2.5).

## 6. Open questions for the operator

- Threshold values for serverless. The classic defaults (`DATABRICKS_MAX_UPTIME` 210 min,
  `DATABRICKS_WARN_UPTIME` 180 min) measured uptime; execution-time minutes (union of
  intervals) are a related but not identical quantity — expect to retune after a week of
  step-2 data, and again after the first billing reconciliation (2.6) shows the real gap.
- Whether `system.billing.usage` and `system.query.history` (not just metadata) are readable
  by this operator — only matters for the reconciliation report, not for enforcement.
- Whether it's worth a follow-up live test of an in-flight *Spark* query against the same
  block (2.5's open question) before Step 4, or whether treating it the same as the
  pure-Python case (assume no termination, plan around prevention only) is good enough. The
  plan currently assumes the latter and doesn't block on running that test.
