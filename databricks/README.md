# Configuring Databricks clusters for Moodle users

Students use Moodle to assign themselves into groups. 

This data is used to automatically generate the same structure in Databricks workspace.

First, save the groups data as CSV to your PC. Remove the "..." line before the headers. Replace non English group names.

Then, create a token (instructions are in the python file)

Run `python3 DataBricksClusterOps.py path/to/csv-file`

Check the workspace: you should see all the users, all the groups, and all the clusters.
Each cluster has permission ('restart') for the group created.

## [OBSOLETE] Last step:  Attach each cluster with the group(s) you want

### Manually (as a backup procedure only)
Open the 'compute' -> "all-purpose-compute" tab. click the 3dots on the right -> "edit permissions". 
click the "select user" and select the group for this cluster (e.g. "cluster_20" --> "g20"). in the Permission column choose 'can restart' and finally the "+ Add" button.

**THEORETICALLY** this should be done once only, since the clusters and groups can be unmodified between semesters.


# The proper way - terraform
https://learn.microsoft.com/en-us/azure/databricks/security/auth-authz/access-control/cluster-acl#terraform-integration

# Running polling periodically 
Use crontab:

As user azureuser (the default user in azure VM): `crontab -e`

add these lines:
```
5/10 * * * * /home/azureuser/periodic_poll.sh

# run every midnight
0 0 * * * /home/azureuser/iem_teachinglab/databricks/restore_permissions.sh
```
In /home/azureuser, create the files:
```
~$ cat periodic_poll.sh 
#!/bin/bash -eu
cd /home/azureuser/iem_teachinglab/databricks
source venv/bin/activate
python poll_clusters.py
deactivate


~$ cat restore_permissions.sh 
#!/bin/bash -eu
cd /home/azureuser/iem_teachinglab/databricks
source venv/bin/activate
rm -f cluster_uptimes
python restore_cluster_permissions.py
deactivate
```
and `$ chmod +x ~/*.sh`

To debug job stdout  `sudo apt-get install postfix`

In the installation, choose "local"

and then periodically:  `cat /var/mail/azureuser`

The output of cron itself is at `/var/log/syslog`


# TEARDOWN
At the end of the semester, you can delete the whole DBR workspace, or delete the clusters only, the users only, or users and their workspace folders.

To delete the workspace,  (after made sure all content is moved to a safe place), go to the Azure portal, choose Databricks workspace, and click the trashcan icon.  It will take a few minutes to delete, and remove the storage account as well (with name such as "dbstorageqz6q3h5ysfvqy")

