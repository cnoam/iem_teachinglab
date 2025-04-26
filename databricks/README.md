2024-12-05: During 2023 and 2034, I wrote python scripts to deploy the needed Databricks clusters from Moodle CSV file.
   Then, migrated the code to Terraform. 

# Configuring Databricks clusters for Moodle users [TF has modern implementation]

Students use Moodle to assign themselves into groups. 

This data is used to automatically generate the same structure in Databricks workspace.

First, save the groups data as CSV to your PC. Remove the "..." line before the headers. Replace non English group names.

Then, create a token (instructions are in the python file)

```
cd databricks 
source venv/bin/activate
pip install -r requirements.txt
``` 
Run `python3 DataBricksClusterOps.py --create_from_csv path/to/csv-file`

Check the workspace: you should see all the users, all the groups, and all the clusters.
Each cluster has permission ('restart') for the group created.

## Old Clusters are deleted
By default, clusters that are not used for 30 days are deleted. see https://kb.databricks.com/en_US/clusters/pin-cluster-configurations-using-the-api

# The proper way - terraform
See the code in iem_teachinglab/terraform/dbr

https://learn.microsoft.com/en-us/azure/databricks/security/auth-authz/access-control/cluster-acl#terraform-integration

# Enforcing quota
In order to save money, I defined the following policy:

  Each cluster can be up (cumulative time) to T minutes every day. <br>
  At midnight the count is reset.<br>
  When a cluster reaches (or exceeds) the quota, it is terminated and cannot be turned on until the next cyle (next day)


## Running The policy checking

The polling process runs in a small VM in the cloud.

Follow the steps below to perform polling periodically.

IMPORTANT: make sure the env vars are correctly set!
1. Create a VM
2. `ssh azureuser@quotaserver****.com`
3. 
```
sudo timedatectl set-timezone Israel
sudo apt update
sudo apt install -y python3-venv
git clone https://github.com/cnoam/iem_teachinglab.git
cd ~/iem_teachinglab/databricks
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```
4.  copy the `.env` file from your working dir to the same path.
    DO NOT add the vars to `.bashrc` since cron will not use them!
5. As user azureuser (the default user in azure VM): `crontab -e`

add these lines:
```
# Check every 15 minutes: 23:00, 23:15, 23:30, 23:45, 00:00 ... 
*/15 * * * * /home/azureuser/periodic_poll.sh 2>&1 | systemd-cat -t dbr_scripts

# run every midnight - a little, to avoid clashing with the other job
55 23 * * * /home/azureuser/iem_teachinglab/end_of_day_ops.sh 2>&1 | systemd-cat -t dbr_scripts
```
In `/home/azureuser`, create the files:
```
~$ cat periodic_poll.sh 
#!/bin/bash -eu
cd /home/azureuser/iem_teachinglab/databricks
source venv/bin/activate
python poll_clusters.py
deactivate
logger Periodic Poll finished

~$ cat end_of_day_ops.sh 
#!/bin/bash -eu
cd /home/azureuser/iem_teachinglab/databricks
source venv/bin/activate
python end_of_day_operations.py
rm -f cluster_uptimes
deactivate
```
and `$ chmod +x ~/*.sh`



The output of cron itself is at `journalctl` and so are the script outputs.

To see the output of the scripts which cron ran, `journalctl -t dbr_scripts` . Add `-r` to see the latest records first.

## Verify cron works as expected 
**IMPORTANT** : cron jobs depends on many factors, so you MUST verify the full execution path!
1. copy the line of 'periodic_poll', changing the time to one shot a few minutes ahead, save, verify you see expected output in journal and possibly in email. Remember to delete it.
2. verify you get the nightly email of 'end_of_day_ops'
3. open journalctl and see the script log output

## Verify email sending
Run the shell scripts from the command line; expect to get email with usage report.


Sending email tends to get stale.<br>
Check by running `python main.py --test_email` (after activating the venv)

# TEARDOWN
At the end of the semester, you can delete the whole DBR workspace, or delete the clusters only, the users only, or users and their workspace folders.

To delete the workspace,  (after made sure all content is moved to a safe place), go to the Azure portal, choose Databricks workspace, and click the trashcan icon.  It will take a few minutes to delete, and remove the storage account as well (with name such as "dbstorageqz6q3h5ysfvqy")
> WARNING: The DBR workspace costs $700 a month just being there! (checked 2025-04-25)
> 
## Recommended Plan
1. Backup all user's DBR workspace by using the GUI (https://learn.microsoft.com/he-il/azure/databricks/notebooks/notebook-export-import#export-all-notebooks-in-a-folder) OR<br>
1.1  Set correct HOST/TOKEN in the .env file<br>
1.2  Set the backup folder name in "scripts/export_dbr_workspaces.py" .  e.g. "databricks_94290_2024w_backup" <br>
1.3  Run the script, make sure the folder is created and filled with python files
1.  Delete the DBR workspace
1.  In the quota-checker machine , edit the crontab and comment out the tasks **
Or just turn it OFF !


# More information
The MS Teams file https://teams.microsoft.com/_?culture=en-us&country=us#/apps/d7958adf-f419-46fa-941b-1b946497ef84/sections/MyNotebook
contains important info:
 - disabling cluster creation by users
 - more!
 
 # Download files or directories from dbfs
 The dbfs is an abstraction above MS storage or Amazon S3. Accessing the files can be using REST API, GUI or command line tool

 ## Downloading using the CLI
 - Install the current version of databricks cli (v0.18 in my ubuntu 22.04).
 - Generate a personal access token using the UI. (https://learn.microsoft.com/he-il/azure/databricks/dev-tools/auth/pat)
 - copy the URL (including 'https://'):    `export DATABRICKS_HOST=https://adb-4286500221395801.1.azuredatabricks.net`
 - copy the token:    `export DATABRICKS_TOKEN="dapi07a*************`
 - check it works ok:   ` databricks  fs ls dbfs:/`

Now you can download a whole directory tree using `databricks fs cp -r dbfs://SRC DST`


# Setting Access permissions to data storage
When a DBR workspace is created in Azure, a new Azure storage account is created. This storage account is managed ONLY by the DBR.
All users of the DBR workspace can read and write to anywhere in this storage, including UNMOUNTING directories.


# Sending email 
The cron job that monitors the cluster may want to send email messages to users.
In 2023 I used gmail, but it is no longer viable. I tried Mailjet, but the outlook server tags the message as Unverified and there is no way I can change it.
So, using Azure: 
Followed the instructions "Quickstart: How to send an email using Azure Communication Services" in Azure. 

Created "Communications Service" and "Email Communications Service", connected them to each other, and ran the sample curl code. It worked (sending from my PC in Technion).
To use it, need to have API key.
