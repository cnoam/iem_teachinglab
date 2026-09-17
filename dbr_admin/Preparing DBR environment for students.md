


[2026-09-17 ] This version of the doc is tailored for Serverless configuration (vs. Classic clusters)

# Preparing environment for students (users) in Azure + Databricks
2025-10-30 Noam

This doc describes how to setup user access to the level we want: students need to:
1. see the databricks workspace
2. be able to open it
3. be able to view the workspace
4. be able to start/stop/connect to their allocated cluster
5. NOT able to create/modify new clusters

To accomplish this, we need to use both Azure's and Databricks permissions

# Create a DBR workspace
*Prerequisite: The Azure admin have to give you "Contributor" or higher role for the subscription, so you can create and manage the resource.*

If not done already, choose the "databricks" resource in the portal's home.

Create. **MAKE SURE you create it in the correct subscription** and in the same **region** as the storage account you will use.

## Set user permissions
To allow a user to see the DBR resource in her portal, she needs READER role.

- Choose the resource-group that contains the DBR workspace (or the subscription if need wide resource usage)
- choose Access Control (IAM) --> Role assignments tab. You should see who has owner/reader/billing etc.
- choose "+Add"
- - In the Role tab, choose "Reader" --> Next
- - in the Members tab, "+select members".
- - search for the ActiveDirectory (aka EntraID) for the relevant course and year and semester. Example "dds00940290". The group we want here is "dds00940290w-2025"
- - "Select" this group
- - "Review + assign"

You can add specific users (who are not in the AD groups) directly: for example the TA and the test account.
- The TA should have "contributor" role (use end date)
- the test account ("efratsupp@technion.ac.il") should have the same role (READER) as the AD group.
  
The above steps implemnt step 1 of the requirements.

# Give users permission to open the DBR workspace
> WARNING: You should use the Terraform method 

Here is the trick: we are now moving to the realm of DBR!

A user MUST be defined in the DBR setting, and have the "Workspace access" and "Databricks sql access".

# Adding a user manually
in the dbr workspace (web ui), click on the top right YourName --> Settings --> "Identity and access" --> Manager "Users" button.

Here you can add a user and give her entitlements.

# Adding all the students in the course
Use the Terraform scripts. A detailed description is in the ../terraform/dbr/Readme.md

This script will add the users, set their groups and provide the correct permissions (Entitlement) (step 4 in the list)


2026-09-17: **WARNING -- disable "Serverless GPU Compute" before each semester starts.**
Databricks now shows both "Serverless" and "Serverless GPU" in the notebook compute
dropdown. **GPU serverless costs roughly 10-20x more per hour than CPU serverless**
(GPU instance rates run ~$5-7/GPU-hour vs well under $1/hour for typical CPU serverless
notebook work) -- a student picking it by accident, or out of curiosity, can burn a real,
large bill in one session, and nothing in our quota system distinguishes GPU from CPU cost.
**MAKE SURE this is disabled** in the workspace admin settings (click your name, top-right)
--> **Previews** --> disable **"Serverless GPU Compute"**. This is a workspace-wide
on/off toggle (not per-user/group), and there is no API for it (checked `workspace-conf`
-- it rejects the plausible key names as invalid) -- it must be done manually in the UI,
once per workspace, at the start of each semester.

# Deny creation of clusters
As of  2025-12-23, the TF script does limit cluster creation, so the rest of this section is informative.

The default policy allows any user to create personal compute cluster with autoshutdown of about 4000 minutes. 

Disable this policy since we want users to use only our cluster configuration. 

We had partial success doing it by editing cluster policy  (https://docs.databricks.com/administration-guide/clusters/policies.html#manage-policy) 

 
And setting  
```
"node_type_id": { 
    "type": "forbidden" 
  } 
```
In the policy editing.

# Add access to storage
We use Unity Catalog: shared read-only course datasets are exposed as external UC volumes.

Full history, the Azure RBAC prerequisites, and every gotcha hit doing this are documented in
`../terraform/docs/course_data_storage_setup.md` -- read it before touching this again, especially
"Key gotchas": a catalog's default storage credential is path-restricted (create a separate,
dedicated credential); `Storage Blob Delegator` is required on the Access Connector's identity in
addition to `Storage Blob Data Reader`; `READ_VOLUME` on the volume alone is not enough, `READ_FILES`
on the external location is also needed per user; and grants must go to each student's email, not to
`all_student_groups` -- group-based grants on volumes/external locations are silently accepted but
do not actually resolve.

As of 2026-09-10, this is fully managed by Terraform (`terraform/dbr-serverless/course_data.tf`, driven
by `course_data_storage_account` / `course_data_containers` / `course_data_access_connector_id` in
`terraform.tfvars`) -- new students in `users.csv` get the grants automatically on the next
`terraform apply`, no manual CLI steps. The one manual, one-time step is the Azure RBAC on the Access
Connector's managed identity (step 1 in the doc above) -- it doesn't change per semester or per
student, so it isn't codified in Terraform here.

## Verify users can read but not write to the containers
Use the test account for this purpose.

# Troubleshooting

## user cannot run ls("/mnt")
If connected to a serverless cluster, the cluster has a policy(?) that forbid access unless user has permission to table. I don't know why it is a table, but wtf.

Solutions:
1. the TF script provisions older cluster versions to overcome this modern obstacle. This solution will not work forever since older cluster will be retired.
2. run in SQL editor (in DBR): `GRANT SELECT ON ANY FILE TO \`efratsupp@technion.ac.il\`;` for each user (bah)
3. stop using mounts; move to Unity Catalog. PREFERRED!
   
## the TA cannot use the workspace
- verify he is added as contributor to the Azure resource: DBR (or the RG contianing the DBR)
- verify he is added as user in the DBR workspace users. 
