resource "databricks_notebook" "sample_notebook" {
  path     = "/Shared/sample_notebook"
  language = "PYTHON"
  format   = "SOURCE"

  content_base64 = base64encode(<<NB
# Databricks notebook source
# Inserts a row into an existing table: <catalog>.<schema>.test_data
# Idempotent: inserts only if id=1 doesn't exist.

dbutils.widgets.text("group_name", "")
dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "")

group_name = dbutils.widgets.get("group_name").strip()
catalog    = dbutils.widgets.get("catalog").strip()
schema     = dbutils.widgets.get("schema").strip()

def _try_scalar(sql_text: str):
    try:
        return spark.sql(sql_text).collect()[0][0]
    except Exception:
        return None

# Resolve catalog/schema if not provided
if not catalog:
    catalog = _try_scalar("SELECT current_catalog()")

if not schema:
    # Heuristic: if group_name is like "group_01" -> schema_01
    if group_name.startswith("group_"):
        schema = group_name.replace("group_", "schema_", 1)
    else:
        schema = _try_scalar("SELECT current_schema()")

if not catalog or not schema:
    raise ValueError(
        f"Could not resolve catalog/schema. Got catalog='{catalog}', schema='{schema}'. "
        "Pass base_parameters: {catalog, schema} (preferred), or at least group_name='group_..'."
    )

table_full_name = f"{catalog}.{schema}.test_data"

spark.sql(f"""
INSERT INTO {table_full_name}
SELECT 1, 'helloworld'
WHERE NOT EXISTS (
  SELECT 1 FROM {table_full_name} WHERE id = 1
)
""")

display(f"Seeded: {table_full_name}")
NB
  )
}
