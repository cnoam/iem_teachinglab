# Submitting pyspark jobs to Databricks

**It does not work yet. The file is uploaded but when running it, I get error.**

**the file is not visible from the notebook. don't know why**

 I found that the file is uploaded with zero size. after a few attempts I tried using "databricks fs cp" and then the file is visible with correct size, but still cannot run it **[ what is the error message? ]**

2024-01-11 I ran this code on Azure Databricks.

Similar to "spark-submit.sh" we can upload a program or a data file from the local directory to a remote storage and run on a DBR cluster.

See  https://docs.databricks.com/en/files/index.html

## Prequisite
have a spark python file ready in local dir.

The python file is loaded to a Workspace. Each user has his own workspace, which is identified by the token used (hence *personal* token)

NOTE: only SINGLE USER clusters have access to Workspace.
The Workspace is where each user's notebooks (and more) are stored.

- install databricks cli
- create a personal token
- configure the databricks cli to use this token (I used env vars).
- start a single user cluster with your user account

Upload the python file to the workspace:
```
databricks workspace import -f SOURCE --language python ./test.py /test.py
```

Verify it is there: `databricks workspace list`

Find the cluster ID:
```
$ databricks clusters list
0110-130144-xdlww9si  Noam Cohen's Cluster                                           RUNNING
1109-104024-w9s1oeb2  cohnstav@campus.technion.ac.il's Personal Compute Cluster      TERMINATED
1216-145525-8rem5bxh  Ilanit Sobol's Power Compute Cluster                           TERMINATED
```
Create a json file:

```
{
    "run_name": "Noam_upload",
    "existing_cluster_id": "0110-130144-xdlww9si",
    "timeout_seconds": 600,
    "spark_python_task": {
      "python_file": "/test.py"
    }
  }
  
```

And submit:  `databricks runs submit --json-file run_config.json`

If it succeeds, you get back a *run id*

Check the status of the run: `databricks runs get --run-id 616163343404380`



