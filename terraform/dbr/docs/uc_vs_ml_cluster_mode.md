# Cluster `data_security_mode`: Unity Catalog vs. PySpark ML vs. cost control

## TL;DR

You cannot get all three of the following at once, on a classic (non-serverless) cluster, as of DBR 15.4:

1. Unity Catalog data access (`/Volumes/...` paths, external locations)
2. Unrestricted `pyspark.ml` (PCA, StringIndexer, and other MLlib constructors)
3. Predictable, admin-controlled uptime/cost (i.e. not Serverless)

This has bitten us once already (July 2026). If you're reading this because a course's
notebooks suddenly can't read `/Volumes/...` paths, or ML notebooks suddenly throw
`Py4JSecurityException`, start here.

## The three `data_security_mode` options and what breaks

| Mode | UC `/Volumes` access | `pyspark.ml` (PCA/StringIndexer/etc) | DBFS `cluster_log_conf` |
|---|---|---|---|
| `NONE` | ❌ broken | ✅ works | ✅ works |
| `USER_ISOLATION` | ✅ works | ❌ blocked by Py4J security manager | ❌ disabled |
| `DATA_SECURITY_MODE_DEDICATED` + `use_ml_runtime=true` | ✅ (in theory) | ✅ (in theory) | untested | 

`USER_ISOLATION` (and `SHARED`) enforce a Py4J security manager that whitelists which JVM
constructors can be called from Python. A large chunk of `spark.ml` is **not** whitelisted,
so calls like:

```
Constructor public org.apache.spark.ml.feature.PCA(java.lang.String) is not whitelisted
```

fail outright. This is a hard platform restriction, not a config bug on our side.

`NONE` mode is the pre-Unity-Catalog "classic" mode: full unrestricted JVM access (so ML
works), but Databricks will not let a `NONE`-mode cluster read Unity Catalog data — only
the legacy `hive_metastore`. Since our students' notebooks reference `/Volumes/xxxx`
paths, `NONE` breaks those.

## Timeline of what happened (2026-07-07/08)

1. IT asked us to migrate off SAS-token + DBFS-mounted storage onto Unity Catalog, for
   governance. We complied: clusters moved to `USER_ISOLATION`, students got
   `/Volumes/xxxx` paths.
2. Students then hit `PCA(...)  is not whitelisted` errors — `USER_ISOLATION`'s Py4J
   security manager blocking core MLlib usage, breaking the ML curriculum.
3. We attempted a fix: `data_security_mode = "DATA_SECURITY_MODE_DEDICATED"` +
   `use_ml_runtime = true` + `single_user_name = <group name>`, intending to keep UC
   access on a classic per-group dedicated cluster while allowing full ML runtime
   (commit `87f8594`).
4. Applying this to all 68 group clusters produced cluster/group errors (e.g.
   `Did not find account group assigned to workspace ... with name group_13`) and,
   on a subsequent `plan`, SCIM read failures across many users/groups
   (`cannot read user: ... is only accessible by admins`).
5. **Root cause of step 4's SCIM errors turned out to be unrelated**: the local
   `databricks auth` CLI profile (`avi-lab`, used by Terraform via
   `workspace_profiles[terraform.workspace]`) had somehow cached an OAuth token for a
   *student* (`efratsupp@technion.ac.il`), not the operator (`cnoam@technion.ac.il`).
   Non-admin identity → SCIM 403s that looked exactly like a broken workspace/UC
   permissions model. Fixed with:
   ```
   databricks auth login --host <workspace-host> --profile avi-lab
   databricks current-user me --profile avi-lab   # verify identity + admin group
   ```
   **Lesson: always verify `current-user me` before concluding a Databricks
   permissions/UC error is a platform or config problem.** It's a 5-second check that
   would have saved significant confusion here.
6. Whether the `DATA_SECURITY_MODE_DEDICATED` + group `single_user_name` approach
   actually works once authenticated correctly is **still unconfirmed** — we didn't
   retry it after fixing the credential issue (see "Open questions" below).
7. As an interim measure, `create_clusters.tf` was reverted to the pre-UC-migration
   state (`data_security_mode = "NONE"` + `cluster_log_conf { dbfs { ... } }`), matching
   commit `c53b0010a87bd`, on branch `revert-dbr-clusters-to-pre-isolation`
   (commit `d128f94`). This restores DBFS logs and unblocks ML, but **breaks UC
   `/Volumes` access for students again** — a known, accepted tradeoff while a
   Microsoft support case is open.
8. A support request was sent to Microsoft/Databricks asking for the officially
   supported way to combine UC access + unrestricted MLlib + classic
   dedicated/cost-controlled clusters (not serverless — we need direct uptime
   control across ~68 concurrent student-group clusters for cost containment).

## Open questions / next steps

- **Retry `DATA_SECURITY_MODE_DEDICATED`** with the correct admin credentials before
  assuming it's broken — the failures observed may have been entirely caused by the
  wrong CLI identity (step 5), not a real limitation of dedicated mode with a group
  `single_user_name`.
- If `single_user_name` genuinely cannot be a workspace-local group (`databricks_group`),
  the fix may be to use a per-group **service principal** or **account-level group**
  instead — this mirrors the existing, known UC limitation that "UC cannot resolve
  workspace-local groups" (grants are already given to individual student emails for
  this reason — see main `CLAUDE.md`).
- Check status of the Microsoft support case before spending more time re-deriving this.
- Whatever the final answer, this file should be updated with the working config once
  found, and the tradeoff table above corrected.

## Related
- `terraform/dbr/CLAUDE.md` — general dbr file map and pitfalls
- Git history: `c25d71a` (NONE → USER_ISOLATION, "enforce user isolation" workspace
  setting), `87f8594` (USER_ISOLATION → DEDICATED attempt), `d128f94` (revert to NONE)
