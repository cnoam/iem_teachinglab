# iem_teachinglab
scripts used in the administration of the teaching lab in the faculty of data and decisions


# Preparing data for a course
2024-06-26

Data is stored in cold storage in storage account ddsteachinglabdatastg (ADLS Gen2) which is COLD storage to reduce expenses.

I created a new storage account in subscription 96224 and copied the folder "fwm-stb-data". I downloaded "Azure Storage Explorer" and after a few hicups (had to kill the process from shell) the GUI opened. I signed in and then selected Copy of the source folder, and Paste into the new storage account in "Blob Containers"

# Connecting Storage Account to Jupyter Notebooks
1. generate SAS token with ReadOnly, for the container needed.
2. create a new notebook and connect to a cluster (you need to turn it on)
3. run the cell from ".../databricks/mounting and reading.ipynb"
4. verify reading is ok.
5. verify writing is denied.
