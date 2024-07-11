# Configuring Databricks clusters for Moodle users

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
2. `ssh azureuser@172.206.249.112`
3. `sudo apt update`
4. `sudo apt install -y python3-venv`
5. `git clone https://github.com/cnoam/iem_teachinglab.git`
6. `cd ~/iem_teachinglab/databricks`
7. `python3 -m venv venv`
8. `source venv/bin/activate`
9. `pip install -r requirements.txt`
10. `deactivate`
11. add at the end of ~/.bashrc:
```asciidoc
export DATABRICKS_HOST="adb-4286500221395801.1.azuredatabricks.net"
export DATABRICKS_TOKEN="****"
export SMTP_PASSWORD="****"
```
or simply copy the `.env` file from your working dir.

12. As user azureuser (the default user in azure VM): `crontab -e`

add these lines:
```
# Check every 15 minutes: 23:00, 23:15, 23:30, 23:45, 00:00 ... 
*/15 * * * * /home/azureuser/periodic_poll.sh

# run every midnight + a little, to avoid clashing with the other job
9 0 * * * /home/azureuser/iem_teachinglab/restore_permissions.sh
```
In /home/azureuser, create the files:
```
~$ cat periodic_poll.sh 
#!/bin/bash -eu
cd /home/azureuser/iem_teachinglab/databricks
source venv/bin/activate
python poll_clusters.py
deactivate
logger Periodic Poll finished

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

## Verify email sending
Sending email tends to get stale.

# TEARDOWN
At the end of the semester, you can delete the whole DBR workspace, or delete the clusters only, the users only, or users and their workspace folders.

To delete the workspace,  (after made sure all content is moved to a safe place), go to the Azure portal, choose Databricks workspace, and click the trashcan icon.  It will take a few minutes to delete, and remove the storage account as well (with name such as "dbstorageqz6q3h5ysfvqy")

**In the quota-checker machine , edit the crontab and comment out the tasks **
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


# Exact steps taken to create workspace with users for course 96224

2024-06-24
- In the Azure portal, I created Databricks workspace, with a new Resource Group, in the course' subscription
- created API token, valid for 60 days, and updated file .env
- updated the DATABRICKS_HOSTNAME in .env
- downloaded the students group CSV file, edited invalid group names (though I think it does not matter)
  - removed the first line, which is before the headers line
- added command line args to the parser
- strengthen the CSV file reader for Moodle

2024-06-26: debugging broken DBR API. after fixing, I created groups and clusters, but permissions are not yet connected.



# Sending email 
The cron job that monitors the cluster may want to send email messages to users.
In 2023 I used gmail, but it is no longer viable. I tried Mailjet, but the outlook server tags the message as Unverified and there is no way I can change it.
So, using Azure: 
Followed the instructions "Quickstart: How to send an email using Azure Communication Services" in Azure. 
Created "Communications Service" and "Email Communications Service", connected them to each other, and ran the sample curl code. It worked (sending from my PC in Technion).