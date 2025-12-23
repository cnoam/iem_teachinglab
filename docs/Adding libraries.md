# Adding libraries to DataBricks clusters

Cluster users may need libraries and sometime they cannot install them.

Also, some code (e.g. nltk) downloads data files needed by the worker, but code running in the notebook will download to machine that runs the notebook -- the Driver node. In this case, the downloaded file is not availabe to the Worker nodes.

One solution is to create a bash script that run ("init script") when a cluster is turned on (or resized)

See documentation in https://learn.microsoft.com/en-us/azure/databricks/init-scripts/global#--add-a-global-init-script-using-the-ui


# Adding an init script

In the Databricks UI   Admin Console / Global Init Scripts / Edit Script

Example:
```
#!/bin/bash

/databricks/python/bin/pip install nltk
/databricks/python/bin/python -m nltk.downloader punkt
/databricks/python/bin/python -m nltk.downloader stopwords
```


NOTE: The downside of installing libs and data from the inis script, is that *each time* a cluster starts, it will rerun this script which can take a long time.

Libraries should be installed in the workspace, making them available to all.

