# DBR workspaces need to use UnitCatalog 

2026-06-01

I created now a new DBR WS. I don't have account privilges, so use WS admin.

https://learn.microsoft.com/he-il/azure/databricks/data-governance/unity-catalog/disable-hms

- in user - settings - security:
 -- disabled lagacy access features
 -- disabled DBFS root and mounts
 
 in user - settings - compute : "Enforce user isolation" True
 
 
 
