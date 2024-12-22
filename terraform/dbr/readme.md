# Using Terraform to deploy DataBricks clusters for students

Students are divided to groups (usually 3 or 4 people).  Each group is allocated its own cluster.

This simple setup requires:
- creating clusters
- creating groups
- creating users
- connecting the above
- setting correct permssions

In practice, the group list is dynamic, so we need to be able to update the setup accordingly, without affecting existing users.


# Usage

1. Download a CSV file from Moodle with 1 or more users (must be email address) in each row. This is an export of the "Students create groups"<br>
Transform this file using `python convert_moodle_to_tf_format.py path/to/the/csv/file` .

The output is named  "users.csv" <br>
Place the `users.csv` file in the `terraform/dbr` folder

2. Create a Databricks workspace (I use Azure portal).
1. generate a Databricks personal token
  - enter the workspace, user settings,  developer tools, manage access tokens, generate new token with short life span (e.g. 2 days).
  - store it as  `TF_VAR_databricks_token=dapia****` in a **safe** place for env variables (e.g. in .bashrc)

1. login to the correct DBR profile:
  `databricks auth login --host adb-3738544368441327.7.azuredatabricks.net`
  This will open the browser and let you login.
  The "adb***" is copied from the URL shown in the browser when entering the workspace.

  Calling this command writes a file ~/.databrickscfg

Originally it looked like:

```
; The profile defined in the DEFAULT section is to be used as a fallback when no profile is explicitly specified.
[DEFAULT]

[adb-3738544368441327 ]
host      = adb-3738544368441327.7.azuredatabricks.net
auth_type = databricks-cli
```

And to make the `terraform apply` work, I edited it to:
```
; The profile defined in the DEFAULT section is to be used as a fallback when no profile is explicitly specified.
[DEFAULT]
host      = adb-3738544368441327.7.azuredatabricks.net
auth_type = databricks-cli
```

In **adition**, you must export these env vars (case sensitive!)
```
TF_VAR_databricks_token
TF_VAR_databricks_host
````

1. run `terraform plan`. check that the plan is reasonable.
1. `terraform apply`. After it finished, check that the resources in the Databricks portal are as expected: users created, they are in the correct group, the group has correct permissions in the correct cluster. All cluster should be turned OFF.


## Modifying properties in existing deployment
You may want to add/remove user, or change the auto-termination, max_workers etc.

Simply update the relevant data file (the CSV or the terraform.tfvars) and `terraform apply` again.


# Installing libraries

First, see https://technionmail-my.sharepoint.com/:w:/r/personal/cnoam_technion_ac_il/_layouts/15/Doc2.aspx?action=edit&sourcedoc=%7Bdff4d25f-d6a5-4b3a-8372-13e6b19c814c%7D&wdOrigin=TEAMS-WEB.undefined_ns.rwc&wdExp=TEAMS-TREATMENT&wdhostclicktime=1734868535555&web=1

Examine the code in `install_libs.tf`
<br><br>

# History timeline
2024-06-27 16:31

Try to migrate all the configurations done in my python code to using terraform.
The python code is complex, and I found out that MS/DBR silently breaks the REST API.

https://registry.terraform.io/providers/databricks/databricks/latest/docs

 Note: the credentials are read from ~/.databrickscg. Make sure they are for the workspace of interest, or the operations will be carried on the wrong WS! Also, the env vars have higher precedence.

2024-06-27 16:37 the installed databricks cli is too old (0.18)
2024-06-27 16:58 installed the newest version (0.222)

I logged in to the correct DBR workspace:

`databricks auth login --host adb-2308486504415649.9.azuredatabricks.net`

When calling `apply` I keep getting

Error: Inconsistent dependency lock file
│ 
│ The following dependency selections recorded in the lock file are inconsistent with the current configuration:
│   - provider registry.terraform.io/databricks/databricks: required by this configuration but no version is selected

so I deleted the state files and ran tf init. Still get the same error.

Even creating a new dir and starting only with the main.tf did not help.


2024-06-27 18:13 finally , after tf init --upgrade and voodoo, I can create a worspace user and delete it. 
If I try to change a field (display_name) I get error that the user already exists. if I then try to destroy it, I get error that it does not exists.

The display name is not taken from the tf file.

2024-09-01 
At last the whole scenario is working: reading a CSV file; creating users, groups, clusters and associating them correctly.



