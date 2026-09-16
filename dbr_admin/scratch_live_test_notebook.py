# Databricks notebook source
# MAGIC %md
# MAGIC # Serverless quota live smoke test
# MAGIC
# MAGIC Generates a few genuine Spark/SQL queries so they show up in Query History,
# MAGIC attributed to this user (`efratsupp@technion.ac.il`, member of `group_01`),
# MAGIC for a live smoke test of `dbr_admin`'s serverless quota-monitor ingest.
# MAGIC
# MAGIC **Before running: attach this notebook to Serverless** (compute dropdown,
# MAGIC top left) -- these queries only matter for the test if they run on
# MAGIC serverless compute, not a classic cluster.
# MAGIC
# MAGIC Each cell is a genuinely compute-bound query (not free/pushdown-optimized --
# MAGIC confirmed live in an earlier session that a plain `count(*)` over a range
# MAGIC gets optimized away in under 2s regardless of row count) so it takes a real,
# MAGIC measurable number of seconds. Run all cells once; that's enough data.

# COMMAND ----------

# MAGIC %md ### Cell 1 -- ~10-20s, warms up serverless compute if it was cold

# COMMAND ----------

spark.sql("""
  SELECT sum(hash(concat(cast(id as string), repeat(chr(65), 50)))) AS checksum
  FROM range(0, 3000000000)
""").collect()

# COMMAND ----------

# MAGIC %md ### Cell 2 -- a second, independent query (own row in Query History)

# COMMAND ----------

spark.sql("""
  SELECT sum(hash(concat(cast(id as string), repeat(chr(66), 50)))) AS checksum
  FROM range(0, 3000000000)
""").collect()

# COMMAND ----------

# MAGIC %md ### Cell 3 -- trivial query, just to confirm even a fast one gets recorded

# COMMAND ----------

spark.sql("SELECT current_user() AS who, current_timestamp() AS ts").show()

# COMMAND ----------

# MAGIC %md Done. Nothing further to do here -- the quota-monitor smoke test reads
# MAGIC these back via the Query History API on the admin side.
