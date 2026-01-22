# History of Databricks Permission Granting Attempts

This document chronicles the attempts, errors, and final working strategy for applying permissions in this Terraform project. It serves as a reference for why the code is structured the way it is.

### Initial Goal
Automate all permissions for student groups (`group_01`) and their Service Principals (`sp_01`) on a shared SQL Warehouse and a dedicated Unity Catalog schema (`schema_01`).

---

### Attempt 1: Fully Automated Group & Secret Grants

*   **Action:**
    1.  Enabled `databricks_service_principal_secret` to generate secrets automatically.
    2.  Used `databricks_grants` to assign schema permissions directly to the `group_01` principal.
*   **Outcome:** Failure.
*   **Errors & Reasons:**
    1.  `Error: cannot create service principal secret: must have account_id on provider`.
        *   **Reason:** The Databricks provider requires account-level admin configuration to automate secret generation in this environment. This is a hard limitation.
    2.  `Error: cannot create grants: Could not find principal with name group_01`.
        *   **Reason:** Unity Catalog is an account-level service. It cannot "see" or resolve **Workspace-Local** groups by name. The `databricks_grants` resource fails because it cannot find the group principal `group_01`.

---

### Attempt 2: Using Human-Readable SP Names

*   **Action:** To improve plan readability, changed references from the Service Principal's `application_id` (UUID) to its `display_name` (`sp_01`) in permission resources.
*   **Outcome:** Failure.
*   **Error:** `Error: cannot update permissions: Principal: ServicePrincipalName(sp_01) does not exist`.
*   **Reason:** The Databricks API requires the unique `application_id` (UUID) when granting permissions to Service Principals. Display names are not valid identifiers in this context.

---

### Attempt 3: Isolate Schema Visibility with `BROWSE`

*   **Action:** To prevent users from seeing all schemas, removed `BROWSE` from the Catalog grant and added it to the `schema_grants` resource, intending for users to see only their own schema.
*   **Outcome:** Failure.
*   **Error:** `Error: cannot update grants: Privilege BROWSE is not applicable to this entity ... metastore in use [1.0]`.
*   **Reason:** This specific metastore version (`1.0`) does not support the `BROWSE` privilege at the Schema level. `BROWSE` can only be applied at the Catalog level, which makes all schemas within visible. The initial error was misleading but ultimately pointed to a version constraint.

---

### Final Working Strategy (The Current Code)

The final code is a hybrid of automation and workarounds to accommodate the above limitations.

1.  **Secret Generation is Manual:** The `databricks_service_principal_secret` resource is commented out. An administrator must generate secrets via the UI as documented in `admin_setup_checklist.md`.
2.  **Schema Grants are to INDIVIDUALS:** The `databricks_grants` resource for schemas **bypasses groups entirely**. It uses a `dynamic` block to loop over the individual student emails from the CSV and grants them permissions directly. This works because Unity Catalog can resolve individual user principals.
3.  **Catalog Visibility is to INDIVIDUALS:** To ensure UI visibility and bypass unreliable group inheritance, `BROWSE` on the Catalog is granted directly to each individual student in a second `dynamic` block.
4.  **Service Principal Grants use UUIDs:** All grants and permissions for Service Principals correctly use the `application_id` (UUID) as required by the API.
