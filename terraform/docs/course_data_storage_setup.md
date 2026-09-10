# Shared read-only course dataset (Unity Catalog external volumes)

Documents the setup done 2026-09-10 to expose the course's shared input datasets to all students
read-only via Unity Catalog, on the `94290_2026` workspace (`adb-7405616428502221...`). Verified working
end-to-end (read as a real non-admin test user) on 2026-09-10.

## Source of truth

- Storage account: `lab94290` (resource group `databricks-rg`, subscription `b3931bf1-b901-4dc2-bf3e-b020fa67cb8b`, HNS/ADLS Gen2 enabled)
- Containers exposed to students: `airbnb`, `booking`
- Other containers on the same account (`submissions`, `bd-linkedin-companies`, `bd-linkedin-people`) are
  **not** exposed by this setup -- do not widen RBAC to the whole storage account, grant per-container only.

Do NOT confuse this with `external-course2024-storage-v2` (→ `abfss://fwm-stb-data@coursedata2024...`) --
that is unrelated, stale infrastructure from a previous year's course, pointing at a different storage
account.

## What was already in place

- UC catalog `94290_lab` (managed catalog).
- Storage credential `94290_lab`, backed by an Azure Databricks Access Connector
  (`unity-catalog-access-connector` in resource group `databricks-rg-94290-lab-c42ettx4sl3ns`), managed
  identity principal id `dc186ab9-7bb2-4aef-8707-ea13536ca584`. It had **zero** Azure RBAC role
  assignments -- it could not reach any storage account yet.

## Final working setup (reproduce in this order)

### 1. Azure RBAC on the Access Connector's managed identity

Two roles are both required, scoped per-container (not the whole storage account):

- `Storage Blob Data Reader` -- read access to blob data.
- `Storage Blob Delegator` -- lets Databricks generate the short-lived **user delegation SAS** it uses to
  vend scoped credentials to Serverless compute. Without this, reads fail with
  `PERMISSION_DENIED: Request for user delegation key is not authorized`, even though data-read RBAC is
  correct. This is easy to miss since it's a separate role from Reader/Contributor.

```bash
for role in "Storage Blob Data Reader" "Storage Blob Delegator"; do
  for container in airbnb booking; do
    az role assignment create --assignee-object-id dc186ab9-7bb2-4aef-8707-ea13536ca584 \
      --assignee-principal-type ServicePrincipal --role "$role" \
      --scope "/subscriptions/b3931bf1-b901-4dc2-bf3e-b020fa67cb8b/resourceGroups/databricks-rg/providers/Microsoft.Storage/storageAccounts/lab94290/blobServices/default/containers/$container"
  done
done
```

Azure RBAC can take a few minutes to propagate; retry on `403`/`not authorized` errors rather than assuming
misconfiguration.

### 2. A dedicated, non-default storage credential

Do **not** reuse the existing `94290_lab` storage credential for this -- it is the catalog's default
managed-storage credential, and Databricks hard-restricts default credentials to only the workspace's own
UC-managed storage path, regardless of the Azure RBAC granted above. Create a separate credential instead,
reusing the same Access Connector (one connector can back multiple credentials -- no new Azure
infrastructure needed):

```bash
databricks storage-credentials create --json '{
  "name": "course_data_credential",
  "azure_managed_identity": {"access_connector_id": "/subscriptions/b3931bf1-b901-4dc2-bf3e-b020fa67cb8b/resourcegroups/databricks-rg-94290-lab-c42ettx4sl3ns/providers/Microsoft.Databricks/accessConnectors/unity-catalog-access-connector"},
  "read_only": true
}'
```

### 3. External locations (read-only), using the new credential

```bash
databricks external-locations create airbnb_data  "abfss://airbnb@lab94290.dfs.core.windows.net/"  course_data_credential --read-only
databricks external-locations create booking_data "abfss://booking@lab94290.dfs.core.windows.net/" course_data_credential --read-only
```

`--read-only` means UC itself refuses write attempts at the platform level, independent of any grant --
a structural guarantee, not just a policy choice.

### 4. Schema and external volumes

```bash
databricks schemas create course_data 94290_lab --comment "Shared read-only course dataset schema"

databricks volumes create --json '{"catalog_name":"94290_lab","schema_name":"course_data","name":"airbnb","volume_type":"EXTERNAL","storage_location":"abfss://airbnb@lab94290.dfs.core.windows.net/"}'
databricks volumes create --json '{"catalog_name":"94290_lab","schema_name":"course_data","name":"booking","volume_type":"EXTERNAL","storage_location":"abfss://booking@lab94290.dfs.core.windows.net/"}'
```

### 5. Grants -- per student email, not per group

Grant to each student's email directly. **Grants to the `all_student_groups` workspace-local group are
accepted without error but do not actually work** -- see "Key gotcha" below. `USE_CATALOG`/`BROWSE` on
`94290_lab` was already granted to students from earlier setup; the rest needs adding per dataset:

```bash
for user in efratsupp@technion.ac.il; do  # extend this list as real students are added
  databricks grants update schema 94290_lab.course_data --json "{\"changes\":[{\"principal\":\"$user\",\"add\":[\"USE_SCHEMA\"]}]}"
  databricks grants update volume 94290_lab.course_data.airbnb  --json "{\"changes\":[{\"principal\":\"$user\",\"add\":[\"READ_VOLUME\"]}]}"
  databricks grants update volume 94290_lab.course_data.booking --json "{\"changes\":[{\"principal\":\"$user\",\"add\":[\"READ_VOLUME\"]}]}"
  databricks grants update external_location airbnb_data  --json "{\"changes\":[{\"principal\":\"$user\",\"add\":[\"READ_FILES\"]}]}"
  databricks grants update external_location booking_data --json "{\"changes\":[{\"principal\":\"$user\",\"add\":[\"READ_FILES\"]}]}"
done
```

Note the last two: `READ_VOLUME` on the volume is **not sufficient by itself** -- `READ_FILES` on the
underlying external location is also required per user. This is easy to miss since the volume-level grant
alone looks complete and most docs describe volume access without mentioning the external-location grant.

## Key gotchas (read before touching this again)

1. **The default storage credential is path-restricted.** Never point a new external location at a
   catalog's default credential (here, `94290_lab`) -- create a separate credential, reusing the same Access
   Connector if one already has the needed RBAC.
2. **`Storage Blob Delegator` is required in addition to `Storage Blob Data Reader`/`Contributor`.** Serverless
   compute's credential vending needs to generate a user delegation SAS; Reader/Contributor alone don't
   include that action.
3. **`READ_VOLUME` on the volume is not enough -- also grant `READ_FILES` on the external location**, per
   user.
4. **Grants to a workspace-local group (e.g. `all_student_groups`) are silently accepted but do not
   actually resolve** -- confirmed by a failed real read test despite the grant existing (see
   `CLAUDE.md`, "UC cannot resolve workspace-local groups"; this is the same known limitation, now confirmed
   to also apply to volumes/external locations, not just schemas). Always grant per student email, and
   verify with an actual read test, not just a successful `grants update` call.

## How students read the data

```python
df_airbnb = spark.read.format("csv").option("header", True).load("/Volumes/94290_lab/course_data/airbnb/AirBNB 1.csv")
df_booking = spark.read.format("json").load("/Volumes/94290_lab/course_data/booking/Booking 1.jsonl")
```

(Adjust format/options/filenames to match the actual files in each container.)

## Codified in Terraform (2026-09-10)

Steps 2-5 above (storage credential, external locations, schema, volumes, and the per-student-email grant
loop) are now managed by `terraform/dbr-serverless/course_data.tf`, using
`course_data_storage_account` / `course_data_containers` / `course_data_access_connector_id` in
`terraform.tfvars`. The manually-created objects were brought under management with `terraform import`
rather than recreated. The per-email grant loop iterates `local.group_members_flattened`, so every student
in `users.csv` gets `USE_SCHEMA`/`READ_VOLUME`/`READ_FILES` automatically on the next `terraform apply` --
no manual CLI steps needed for new students going forward.

Step 1 (Azure RBAC on the access connector) is **not** codified -- it's a one-time Azure-side prerequisite,
not something that changes per semester or per student, so it doesn't need a Terraform resource here
(would require adding the `azurerm` provider to `dbr-serverless/`, which doesn't otherwise need it).

## Follow-up

- There is currently a redundant `Storage Blob Delegator` assignment scoped to the whole `lab94290` storage
  account (in addition to the per-container ones in step 1) -- harmless, but can be removed for cleanliness
  since the per-container assignments are sufficient.
