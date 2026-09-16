# MS support ticket draft: terminating a running serverless notebook command

## Executive summary

We enforce a per-group daily compute-time quota on student lab clusters (cost + runaway-code
control). On classic clusters this meant powering off the cluster on breach. We've migrated
to serverless compute and cannot find any way to replicate the "terminate" half of that policy:
no API cancels a specific in-flight serverless notebook command, and every other lever we
tried (revoking group entitlement, the Statement Execution cancel endpoint, the execution
timeout) either only blocks *new* work or doesn't cover our case. We need to know if an
on-demand termination API exists, is planned, or if there's a supported alternative pattern.

## Requirement

> Each group's compute can be up (cumulative time) to *T* minutes/day. At midnight the count
> resets. On breach, compute is terminated and blocked until the next day.

(Enforced today on classic clusters via our own polling process + Clusters API.)

## What we need

An officially supported way to forcibly terminate a specific, currently-running serverless
notebook command/session, on demand, from an admin/automation context.

## What we tried, and confirmed doesn't do this

1. **Revoke group entitlement (workspace-access/sql-access) via SCIM.** Tested live: an
   already-running notebook loop kept executing untouched for ~4.5 min after revocation. New
   commands and page loads failed immediately. Blocks new work only.
2. **Query History API.** Notebook-sourced records show `is_cancelable: false` even while
   `RUNNING`. No cancel endpoint accepts a query-history id (`.../statements/{id}/cancel`
   only takes ids from the Statement Execution API, not notebook-issued commands).
3. **Serverless interactive execution timeout.** Cancels a Spark Connect query past a fixed
   duration, but it's a ceiling, not an on-demand trigger, and confirmed (live test) to not
   apply at all to plain Python code with no Spark calls.
4. **Jobs API `runs/cancel`.** Works for job runs; not applicable to interactive notebooks.

## Questions

1. Any API to cancel a specific running command in a serverless notebook, from outside it?
2. Any API to force-detach a specific user's serverless session on demand?
3. Is termination-based quota enforcement for serverless supported or on the roadmap?
4. If not: what's the recommended pattern for a hard per-user/group compute-time cap on
   serverless, given entitlement revocation only blocks new work?

## Environment used

- Technion tenant, Workspace `94290_2026` (id `7405616428502221`, `https://adb-7405616428502221.1.azuredatabricks.net`)
- Unity Catalog + serverless compute for notebooks/jobs enabled

## Why we migrated off classic

Classic clusters hit an unresolved `data_security_mode` conflict — no single mode gives UC
`/Volumes` access, DBFS logs, and unrestricted `pyspark.ml` together. Serverless is UC-native
and starts in ~10s vs. 3-10min, so we moved independently of resolving that case.

From the docs we understand that DBFS of deprecated, and we need to migrated to UC

[2026-09-16 ] Written by Claude, reviewed by Noam Cohen.
