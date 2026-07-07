# Databricks on Azure with SAS Tokens — Classroom Checklist

Audience: instructor / lab engineer managing a Databricks workspace for a class of about 100 students.

Scope: keep the current SAS-token + mount workflow for now, while reducing operational and security risk.

---

## 0. Recommended classroom layout

Use two separate containers or clearly separated paths:

```text
Storage Account
├── input container/path      # read-only datasets for students
└── output container/path     # student-written results
```

Recommended naming example:

```text
input container:  course-input
output container: course-output
```

Databricks mount examples:

```text
/mnt/course-input
/mnt/course-output
```

---

## 1. Pre-semester storage checklist

- [ ] Confirm the Azure Storage Account exists.
- [ ] Confirm hierarchical namespace / ADLS Gen2 status if using `abfss://` paths.
- [ ] Create or verify the input container.
- [ ] Create or verify the output container.
- [ ] Upload all course input files to the input container.
- [ ] Keep the input data immutable during exercises unless the change is intentional.
- [ ] Decide whether output should be shared or per-student.

Recommended output structure:

```text
course-output/
├── student_id_001/
├── student_id_002/
├── student_id_003/
└── ...
```

If students all write to the same directory, accidental overwrite risk is high.

---

## 2. SAS token checklist

Create separate SAS tokens for input and output.

### Input SAS token

- [ ] Scope: input container only.
- [ ] Permissions: read and list only.
- [ ] Suggested permissions:

```text
Read:   yes
List:   yes
Write:  no
Create: no
Delete: no
Add:    no
```

- [ ] Expiry: no longer than needed for the semester plus a small buffer.
- [ ] Protocol: HTTPS only.
- [ ] IP restriction: use only if your students connect from predictable IP ranges.
- [ ] Save the token in a secure place temporarily.

### Output SAS token

- [ ] Scope: output container only.
- [ ] Permissions: read, list, create, write.
- [ ] Consider whether delete is required.
- [ ] Suggested permissions:

```text
Read:   yes
List:   yes
Create: yes
Write:  yes
Add:    optional
Delete: preferably no
```

- [ ] Expiry: no longer than needed for the semester plus a small buffer.
- [ ] Protocol: HTTPS only.
- [ ] Save the token in a secure place temporarily.

### Avoid

- [ ] Do not generate account-level SAS unless absolutely necessary.
- [ ] Do not give students SAS tokens directly.
- [ ] Do not paste SAS tokens into notebooks that students can view.
- [ ] Do not commit SAS tokens to Git.
- [ ] Do not put SAS tokens in cluster Spark config visible to students unless unavoidable.

---

## 3. Databricks secret scope checklist

Use Databricks secrets instead of hardcoding SAS tokens.

- [ ] Create a secret scope, for example:

```text
course-secrets
```

- [ ] Store the input SAS token:

```text
scope: course-secrets
key:   input-sas
```

- [ ] Store the output SAS token:

```text
scope: course-secrets
key:   output-sas
```

- [ ] Restrict who can manage the secret scope.
- [ ] Confirm students cannot read secret values directly.
- [ ] Confirm only the mounting notebook or setup notebook uses the secrets.

Example using Databricks CLI:

```bash
databricks secrets create-scope course-secrets

databricks secrets put-secret course-secrets input-sas

databricks secrets put-secret course-secrets output-sas
```

---

## 4. Mounting checklist

Run the mounting code from an instructor/admin notebook, not from a notebook students edit.

### Input mount

- [ ] Confirm the mount point does not already exist.
- [ ] Mount input container as read-only by using a read/list SAS token.
- [ ] Test reading files.
- [ ] Test that writing to input fails.

Example pattern:

```python
storage_account = "<storage-account-name>"
input_container = "course-input"
input_mount = "/mnt/course-input"

input_sas = dbutils.secrets.get("course-secrets", "input-sas")

source = f"wasbs://{input_container}@{storage_account}.blob.core.windows.net"

configs = {
    f"fs.azure.sas.{input_container}.{storage_account}.blob.core.windows.net": input_sas
}

if input_mount not in [m.mountPoint for m in dbutils.fs.mounts()]:
    dbutils.fs.mount(
        source=source,
        mount_point=input_mount,
        extra_configs=configs
    )
```

### Output mount

- [ ] Confirm the mount point does not already exist.
- [ ] Mount output container using the output SAS token.
- [ ] Test writing a small file.
- [ ] Test reading the written file.
- [ ] Delete the test file if delete permission exists; otherwise leave a harmless test file.

Example pattern:

```python
storage_account = "<storage-account-name>"
output_container = "course-output"
output_mount = "/mnt/course-output"

output_sas = dbutils.secrets.get("course-secrets", "output-sas")

source = f"wasbs://{output_container}@{storage_account}.blob.core.windows.net"

configs = {
    f"fs.azure.sas.{output_container}.{storage_account}.blob.core.windows.net": output_sas
}

if output_mount not in [m.mountPoint for m in dbutils.fs.mounts()]:
    dbutils.fs.mount(
        source=source,
        mount_point=output_mount,
        extra_configs=configs
    )
```

---

## 5. Validation checklist

Run these tests before students start.

### Read test

- [ ] List input files:

```python
display(dbutils.fs.ls("/mnt/course-input"))
```

- [ ] Read a sample file:

```python
df = spark.read.option("header", True).csv("/mnt/course-input/sample.csv")
display(df.limit(10))
```

### Input write-protection test

- [ ] Confirm this fails:

```python
dbutils.fs.put("/mnt/course-input/should_not_write.txt", "test", overwrite=True)
```

Expected result: permission error.

### Output write test

- [ ] Confirm this succeeds:

```python
dbutils.fs.put("/mnt/course-output/test_write.txt", "test", overwrite=True)
display(dbutils.fs.ls("/mnt/course-output"))
```

### Student simulation test

- [ ] Test with a non-admin student-equivalent user.
- [ ] Confirm the student can read input.
- [ ] Confirm the student can write output.
- [ ] Confirm the student cannot access secrets directly.
- [ ] Confirm the student cannot modify the mounting notebook.

---

## 6. Notebook template for students

Use a small standard snippet in all student notebooks.

```python
student_id = "<replace-with-your-id>"

input_path = "/mnt/course-input"
output_path = f"/mnt/course-output/{student_id}"

# Example read
df = spark.read.option("header", True).csv(f"{input_path}/sample.csv")

# Example write
df.write.mode("overwrite").parquet(f"{output_path}/lab1_result")
```

Student instruction:

- [ ] Replace `student_id` with your assigned ID.
- [ ] Never write directly to `/mnt/course-output` root.
- [ ] Always write under `/mnt/course-output/<student_id>/...`.
- [ ] Use `overwrite` only inside your own folder.

---

## 7. Cluster / compute checklist

- [ ] Use a cluster policy for the class.
- [ ] Limit maximum worker count.
- [ ] Set auto-termination.
- [ ] Restrict expensive instance types.
- [ ] Prefer shared classroom clusters only if isolation requirements are acceptable.
- [ ] Confirm installed libraries before the first lab.
- [ ] Confirm all notebooks run from a clean cluster.

Suggested operational defaults:

```text
Auto-termination: 20-30 minutes
Worker limit:     based on budget
Runtime:          one fixed LTS runtime for the semester
```

---

## 8. Security checklist

- [ ] SAS tokens are stored only in Databricks secrets or another controlled secret store.
- [ ] SAS tokens are not visible in notebooks.
- [ ] SAS tokens are not printed to output cells.
- [ ] SAS tokens are not committed to Git.
- [ ] Input SAS has no write/delete permissions.
- [ ] Output SAS does not have delete permission unless required.
- [ ] Mounting notebook is editable only by instructors/admins.
- [ ] Student notebooks contain only `/mnt/...` paths, not credentials.
- [ ] Token expiry date is documented.
- [ ] Token rotation plan exists.

---

## 9. Token rotation checklist

Use this if a SAS token expires or leaks.

- [ ] Generate a new SAS token with the same minimal permissions.
- [ ] Update the corresponding Databricks secret.
- [ ] Unmount the affected mount.
- [ ] Remount using the updated secret.
- [ ] Restart affected clusters if needed.
- [ ] Test read/write behavior again.
- [ ] Revoke or let expire the old SAS token.

Unmount example:

```python
dbutils.fs.unmount("/mnt/course-input")
dbutils.fs.unmount("/mnt/course-output")
```

Then rerun the instructor mounting notebook.

---

## 10. Troubleshooting checklist

### Students get permission errors when reading input

- [ ] Check that the input mount exists.
- [ ] Check that the input SAS token has `Read` and `List` permissions.
- [ ] Check that the SAS token has not expired.
- [ ] Check that the path is correct.
- [ ] Check that the file exists in the container.

### Students get permission errors when writing output

- [ ] Check that the output mount exists.
- [ ] Check that the output SAS token has `Create` and `Write` permissions.
- [ ] Check that the SAS token has not expired.
- [ ] Check that students are writing under their own folder.
- [ ] Check whether overwrite requires delete permission for the specific operation.

### Mount exists but data is stale or inaccessible

- [ ] Refresh mounts:

```python
dbutils.fs.refreshMounts()
```

- [ ] Restart the cluster.
- [ ] Unmount and remount if the SAS token changed.

### A token was exposed

- [ ] Treat it as compromised.
- [ ] Generate a replacement SAS token.
- [ ] Update the Databricks secret.
- [ ] Remount.
- [ ] Remove exposed token from notebooks, logs, Git history, or shared documents.
- [ ] Review whether storage logs show unexpected access.

---

## 11. End-of-semester checklist

- [ ] Export or archive student outputs if needed.
- [ ] Stop or delete unused clusters.
- [ ] Remove student workspace access if appropriate.
- [ ] Revoke or allow SAS tokens to expire.
- [ ] Unmount course storage if no longer needed.
- [ ] Delete temporary output data if policy allows.
- [ ] Record lessons learned for next semester.

---

## 12. Future migration note

This SAS + mount setup is acceptable as a short-term classroom solution, but it should be treated as legacy/temporary. For future semesters, consider moving to Unity Catalog external locations and volumes when account-level and Azure-level permissions are available.

The main future benefits are:

- no SAS tokens in the teaching workflow;
- better access control using groups;
- clearer read/write separation;
- better auditability;
- easier long-term governance.
