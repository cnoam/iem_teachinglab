# Configuring Databicks clusters for Moodle users

Students use Moodle to assign themselves into groups. 

This data is used to automatically generate the same structure in Databricks workspace.

First, save the groups data as CSV to your PC.

Then, create a token (instruction are in the python file)
Edit the python file to use your CSV.

Run `python3 DataBricksClusterOps.py`

Check the workspace: you should see all the users, all the groups, and all the clusters.

Last step: (currently manually): Attach each cluster with the group(s) you want.


