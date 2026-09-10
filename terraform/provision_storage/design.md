[2026-09-10 ] Possibly outdated!

# Per-Group Student Storage on Azure + Databricks UC — Design Document

**Prepared for IT review**
Date: 2026-03-09

---

## Background

Each semester, student groups (up to 4 people per group) need isolated cloud storage they can read/write from Databricks notebooks. Access must be exclusive per group — no group should be able to read another group's data. The folder structure is created at semester start and destroyed at semester end.

---

## Requirements

- One folder per student group in an existing Azure Storage Account (ADLS Gen2)
- Each group can read/write only its own folder (similar to Linux per-user directories)
- Databricks notebooks running under a group's identity can access the group's folder
- Access is enforced via Unity Catalog (UC); students do not get direct storage credentials
- Fully automated via Terraform — no manual steps after initial one-time setup
- Created and destroyed each semester with a single `terraform apply` / `terraform destroy`

## Constraints

- Operator has: Azure Subscription **Owner**, Databricks **workspace admin**
- Operator does NOT have: Databricks account admin, Azure Entra admin
- Operator CANNOT create Azure App Registrations / Service Principals in Entra
- Students have `Reader` role on the storage account (management-plane only — cannot read blob data)

---

## Key Decisions

### Why not App Registrations / Service Principals?

Creating an App Registration requires Entra (AAD) admin rights, which we don't have.
Instead we use **User-Assigned Managed Identities (UAMI)**, which:
- Are created by Azure Subscription Owner (no Entra admin needed)
- Are managed by Azure — no passwords or certificates to rotate
- Cannot be used by human users, even if they can see it in the portal

### What is a UAMI?

A UAMI is an Azure identity not tied to any single resource. It is assigned to an **Azure Databricks Access Connector**, which bridges Azure and Databricks Unity Catalog. The flow is:

```
Notebook runs
  → UC checks: does this group have WRITE_VOLUME on this volume?
  → Yes → Access Connector presents UAMI to Azure Storage
  → Storage grants access because UAMI has Storage Blob Data Contributor
```

Students cannot impersonate the UAMI. Their own portal accounts only have `Reader`
(management-plane), which grants zero access to blob contents.

### Why student `Reader` role is not a concern

`Reader` is a management-plane role: it lets students see the storage account exists
in the Azure portal, nothing more. Reading blob data requires `Storage Blob Data Reader`
or higher, which students do not have. Direct storage access will show "Authorization failed."

### Option chosen: Shared UAMI (Option A)

One UAMI with `Storage Blob Data Contributor` on the semester container.
Isolation between groups is enforced by **Unity Catalog external location grants** —
each group's Databricks identity can only access its own external location / volume.

This is sufficient because students have no data-plane RBAC on the storage account.

---

## Architecture

```
Azure Storage Account (existing, ADLS Gen2 / HNS enabled)
└── Container: semester-YYYY-X/
    ├── group01/
    ├── group02/
    └── ...

Azure Resources (long-lived, created once):
  User-Assigned Managed Identity (UAMI)  ← no Entra admin needed
  Azure Databricks Access Connector      ← bridges UAMI to Databricks
  RBAC: UAMI → Storage Blob Data Contributor on the storage account

Unity Catalog (per semester):
  Storage Credential  ← references the Access Connector + UAMI
  External Location per group  → abfss://semester-YYYY-X@storage.dfs.core.windows.net/groupNN/
  External Volume per group    → /Volumes/main/groupNN/files/
  GRANT READ_VOLUME, WRITE_VOLUME ON VOLUME → Databricks group-NN
```

Students access their data in notebooks as:
```python
df = spark.read.csv("/Volumes/main/group01/files/mydata.csv")
```

---

## What IT Needs to Do (One-Time Only)

These steps require **Databricks account admin** and are needed only once, not every semester.

### Step 1 — Grant CREATE EXTERNAL LOCATION privilege

In the Databricks account console or via SQL:
```sql
GRANT CREATE EXTERNAL LOCATION ON METASTORE TO `<workspace-admin-group>`;
```

### Step 2 — Create the Storage Credential

After the Access Connector is deployed (we do this via Terraform), IT creates one
Storage Credential in Unity Catalog pointing to our Access Connector:

```sql
CREATE STORAGE CREDENTIAL teaching_lab_credential
  WITH AZURE_MANAGED_IDENTITY (
    connector = '/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Databricks/accessConnectors/ac-teaching-lab'
  );

GRANT ALL PRIVILEGES ON STORAGE CREDENTIAL teaching_lab_credential
  TO `<workspace-admin-group>`;
```

**This is a one-time action. After this, every semester is fully self-service.**

Alternatively, IT can grant `CREATE STORAGE CREDENTIAL ON METASTORE` and we handle it ourselves.

---

## Semester Lifecycle (self-service after IT setup)

```bash
# Start of semester — creates storage dirs, external locations, volumes, grants
terraform apply -var="semester=2026a"

# End of semester — destroys all of the above, storage data included
terraform destroy -var="semester=2026a"
```

The Access Connector and UAMI are long-lived and survive the destroy.

---

## Resources to be Created by Terraform

### Long-lived (created once, not per semester)

| Resource | Type | Notes |
|---|---|---|
| `uami-teaching-lab` | Azure User-Assigned Managed Identity | No Entra admin needed |
| `ac-teaching-lab` | Azure Databricks Access Connector | Bound to the UAMI |
| RBAC assignment | Storage Blob Data Contributor on storage account | For the UAMI |

### Per-semester

| Resource | Type |
|---|---|
| Container `semester-YYYY-X` | ADLS Gen2 filesystem |
| Directory per group | `azurerm_storage_data_lake_gen2_path` |
| External Location per group | `databricks_external_location` |
| External Volume per group | `databricks_volume` |
| UC grants per group | `databricks_grants` |

---

## Security Summary

| Threat | Mitigation |
|---|---|
| Student reads another group's storage via portal | `Reader` role = management plane only; no blob access |
| Student reads another group's volume in notebook | UC external location grants are exclusive per group |
| Student escalates via UAMI | UAMI is a service identity; humans cannot assume it |
| Leftover data after semester | `terraform destroy` removes container and all contents |
