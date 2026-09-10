# Manual verification checklist -- can students actually work?

Run this once with a test user (currently `efratsupp@technion.ac.il`) before real students start, and again
any time compute mode, UC grants, or storage wiring changes. This is not automated -- log in as the test
user (or have them run it) and check off each step.

See also: `~/proto/accessing_dbr/test_connection.py`, an automated script that validates a group's
**service principal** credentials (OAuth, schema isolation) -- a different, narrower check than this one,
which is about the actual interactive student experience.

## 1. Azure access

- [x] User can see the Databricks workspace resource in the Azure Portal (not just other resources in the
      subscription). If not: check the role assignment is **Active**, not PIM **Eligible**, and scoped to
      the resource group that actually contains the workspace -- see `../../dbr/readme.md`, section
      "A user has a visible Reader role but still can't see/open the Databricks workspace".
- [x] Confirm it's the **correct** workspace (compare the URL, `adb-<id>.<n>.azuredatabricks.net`, against
      the `host` in the relevant `.databrickscfg` profile) -- it's easy to open a leftover workspace from a
      previous course/year by mistake.

## 2. Workspace login

- [x] User can open the Databricks workspace UI (Entra SSO).
- [ ] User does NOT see other students'/groups' home folders under Workspace > Users (aside from their own
      and admins) -- if they do, verify they actually opened the intended workspace (see 1 above), not an
      unrelated one. [ DEFFERED -- there are no other users]

## 3. Notebook + Serverless compute

- [X] User can create a new notebook.
- [X] **Serverless** appears in the compute dropdown (if it does not, and only Serverless is absent while a
      classic cluster is selectable, check cluster ACLs / `single_user_name`; see `../../dbr/readme.md`,
      "Cluster ownership (service principals)"). In the current serverless-only setup, Serverless should be
      the only/default option since students have `allow_cluster_create = false` and no clusters exist.
- [X] Attaching to Serverless succeeds and a trivial cell (`print("hello")`) runs.

## 4. Per-group UC schema (read/write, own data)

```python
data = [(1, "a"), (2, "b"), (3, "c")]
df = spark.createDataFrame(data, ["id", "value"])
df.write.mode("overwrite").saveAsTable("94290_lab.schema_NN.verification_test")  # replace NN with your group

df_read = spark.table("94290_lab.schema_NN.verification_test")
display(df_read)
```

- [x] User can run the write above (creates a table in their own group's schema).
- [x] User can read it back with the `spark.table(...)` call and sees the same 3 rows.

**Where does this data actually get written?** `saveAsTable` creates a **managed table**. Unity Catalog
stores managed-table data in the metastore's own managed storage location (an internal, UC-controlled Azure
storage account, scoped under the catalog/schema) -- not on the local disk of the compute node. This
matters because a Serverless node has no persistent local disk to speak of: anything written to local/tmp
storage on a serverless session is ephemeral and disappears when the session ends. Managed tables (and the
external volumes in section 6) are the durable storage; local paths are not.

## 5. Cross-group isolation (should FAIL)

- [ ] User attempts to read/write another group's schema (e.g. `schema_02` if they're in `schema_01`) and
      gets a permission-denied error, not data. [ DEFFERED -- there are no other users]

## 6. Shared course dataset (read-only) -- NEW, added 2026-09-10

Setup documented in `../../docs/course_data_storage_setup.md`.

- [x] Read test -- user can load a dataframe from a **subset** of files in each volume (verified 2026-09-10
      with `efratsupp` reading a specific file from each container):
  ```python
  df = spark.read.format("csv").option("header", True).load("/Volumes/94290_lab/course_data/airbnb/AirBNB 1.csv")
  display(df.limit(10))

  df2 = spark.read.format("json").load("/Volumes/94290_lab/course_data/booking/Booking 1.jsonl")
  display(df2.limit(10))
  ```
  (Adjust `.format(...)`/options/filenames to match the actual files in each container.)
- [x] Write-denied test -- confirm this fails with a permission/read-only error, not silently succeeding:
  ```python
  dbutils.fs.put("/Volumes/94290_lab/course_data/airbnb/should_not_write.txt", "test", overwrite=True)
  ```
  Expected: error. The external location is created with `--read-only`, so this should fail at the UC/Azure
  level even if a grant were ever mistakenly widened to include write privileges.

### Confirmed 2026-09-10: full working grant chain, per student email

Getting this to actually work took several fixes, all captured in `../../docs/course_data_storage_setup.md`
("Key gotchas"). In short: grants must go to each student's email, not the `all_student_groups` workspace
group (accepted without error but doesn't resolve); the Azure Access Connector needs both `Storage Blob Data
Reader` and `Storage Blob Delegator`; the external location must use a non-default storage credential; and
`READ_FILES` on the external location is required in addition to `READ_VOLUME` on the volume. Read that doc
before re-deriving any of this.

## If anything fails

Note which step failed and the exact error message before escalating -- most of the failure modes above
have a documented root cause and fix linked from this checklist.
