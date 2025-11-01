
2025-11-02: Must I keep using "real" clusters and not serverless?

It looks like the new serverless mode has many limitations!
https://gemini.google.com/share/215a64befbb7

- strongly recommended to use Unity Catalog
- no JAR lib , more limitations
==> for now, I will use last year's configuration


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

Create. **MAKE SURE you create it in the correct subscription**

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
- The TA should have "contributor" role
- the test account ("efratsupp@technion.ac.il") should have the same role (READER) as the AD group.
  
The above steps implemnt step 1 of the requirements.

# Give users permission to open the DBR workspace
Here is the trick: we are now moving to the realm of DBR!

A user MUST be defined in the DBR setting, and have the "Workspace access" and "Databricks sql access".

# Adding a user manually
in the dbr workspace (web ui), click on the top right YourName --> Settings --> "Identity and access" --> Manager "Users" button.

Here you can add a user and give her entitlements.

# Adding all the students in the course
Use the Terraform scripts. A detailed description is in the Readme.md

This script will add the users, set their groups and provide the correct permissions (Entitlement) (step 4 in the list)

# Deny creation of clusters
as of  2025-10-30, the TF script does not limit cluster creation.

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
