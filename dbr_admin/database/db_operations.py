import datetime
import os, sys, logging
from peewee import *
from pathlib import Path


ENV_VAR='CLUSTER_UPTIMES_DB'
env_value = os.environ.get(ENV_VAR)
if env_value:
    db_path = Path(env_value).expanduser()
else:
    db_path = Path.home() / ".local" / "share" / "iem_teachinglab" / "cluster_uptimes.db"
    logging.warning(f" {ENV_VAR} is not set. "
        f"Using default database path: {db_path}" )

db_path.parent.mkdir(parents=True, exist_ok=True)
DATABASE_FILE_NAME = str(db_path)


# --- Model Definitions ---

class BaseModel(Model):
    """A base model that specifies the database to use."""
    class Meta:
        pass

class ClusterUptime(BaseModel):
    """
    Maps to the 'cluster_uptimes' table.
    Durations are stored as total seconds (FloatField).
    """
    cluster_id = CharField(primary_key=True)


    # Used for calculating the live 'uptime'. Nullable if the cluster is off.
    start_time = DateTimeField(null=True)

    # Current uptime of the actively running cycle (in seconds)
    uptime_seconds = FloatField(default=0.0)

    # Total accumulated uptime from all previous cycles (in seconds)
    cumulative_seconds = FloatField(default=0.0)

    warning_sent = BooleanField(default=False)
    force_terminated = BooleanField(default=False)

    # When (if at all) the last poll was made for this cluster.
    # This field is used for total uptime calculation.
    last_poll_time = DateTimeField(null=True)

    class Meta:
        table_name = 'cluster_uptimes'
        # do not set 'db' here since we dynamically bind to the DB instance (to use either testing DB or production DB)


class ClusterCumulativeUptime(BaseModel):
    """
    Maps to the 'cluster_cumulative_uptimes' table.
    Links daily usage back to a specific cluster.
    """
    # Foreign key link to the ClusterUptime table
    cluster = ForeignKeyField(ClusterUptime, backref='daily_records', field='cluster_id')

    # Date of the daily use
    date = DateField(default=datetime.date.today)

    # Storing daily usage duration
    daily_use_seconds = FloatField(default=0.0)

    class Meta:
        # Ensures that a cluster can only have one daily use record per date
        indexes = (
            (('cluster', 'date'), True),
        )


# gemini 2025-11-25 13:30
class ClusterInfo(BaseModel):
    """
    Maps cluster IDs to cluster names.
    This table is populated once from the API client.

    Note: In Databricks, cluster names are NOT unique.
    I decided to keep it unique here to avoid confusion, since we rely on cluster names in other places.
    """
    cluster_id = CharField(primary_key=True)
    cluster_name = CharField(unique=True)


# --- Serverless quota tables (additive; see databricks/serverless_quota_plan.md, 2.4) ---
#
# SCOPE, FIRST CUT (operator decision): this schema records usage visible
# through the Query History API -- i.e. Spark/SQL execution. Per the plan's
# section 1a, a pure-Python notebook cell (no Spark calls) issues no query
# and is therefore invisible to this table; nothing here detects or bounds
# it. That is a known, accepted limitation of this first cut, not a bug --
# it is considered PASS without covering pure-Python execution. The
# system.billing.usage backstop (plan 2.6a) is the only thing that
# eventually catches that gap, and is separate, later work.

class QueryUsage(BaseModel):
    """
    One row per Query History API record (query_id is that API's own id,
    stable across polls -- see plan 2.2). Ingest upserts by query_id, so a
    RUNNING row is safely overwritten by its later FINISHED version rather
    than double-counted.
    """
    query_id = CharField(primary_key=True)

    # Databricks user_name (email) the query ran as, and the group_name it
    # was attributed to (plan 2.3) -- null while unresolved/ungrouped
    # (staff, service principals): reported, never blocked.
    user_name = CharField()
    group_name = CharField(null=True)

    # Local date bucket (plan 2.4: derived from start_time_ms via
    # datetime.fromtimestamp(...).date(), NOT UTC -- see the plan section
    # for why). Ingest's responsibility to set correctly; this table does
    # not recompute it.
    day = DateField()

    # Raw epoch-ms fields from the API, kept so elapsed time can be
    # recomputed for a still-RUNNING row (plan 2.2: duration_ms is null
    # while RUNNING -- confirmed live, use start_time_ms instead) or the
    # day bucketing revisited later if ever needed.
    start_time_ms = BigIntegerField()
    duration_ms = FloatField(null=True)

    # Raw status string from the API (RUNNING, QUEUED, FINISHED, CANCELED,
    # FAILED, ...) -- not modeled as an enum so a new status value from the
    # API doesn't break ingestion.
    status = CharField()

    class Meta:
        table_name = 'query_usage'
        indexes = (
            # The read pattern is always "all rows for this group on this
            # day" (union_seconds() in resource_manager/serverless_quota.py).
            (('group_name', 'day'), False),
        )


class GroupQuotaState(BaseModel):
    """
    One row per group per day: whether it's been warned and/or blocked
    today. Mirrors ClusterUptime's warning_sent/force_terminated fields,
    but scoped to a single day (serverless has no "reset the whole live
    table at midnight" step the way ClusterUptime does -- see
    GroupDailyUsage below for the rollup that plays that role).
    """
    group_name = CharField()
    day = DateField()
    warned = BooleanField(default=False)
    blocked = BooleanField(default=False)
    blocked_at = DateTimeField(null=True)

    class Meta:
        table_name = 'group_quota_state'
        indexes = (
            (('group_name', 'day'), True),  # one state row per group per day
        )


class GroupDailyUsage(BaseModel):
    """
    Historical rollup: one row per group per day, written once at end-of-day
    (plan 2.6). Mirrors ClusterCumulativeUptime's role for the classic
    backend -- same (group, date) unique-pair pattern.
    """
    group_name = CharField()
    date = DateField()
    used_seconds = FloatField(default=0.0)

    class Meta:
        table_name = 'group_daily_usage'
        indexes = (
            (('group_name', 'date'), True),
        )


class IngestWatermark(BaseModel):
    """
    Last-seen point for a given ingest backend, so polling can resume from
    `last_seen_ms - slack` (plan 2.2) instead of re-scanning from scratch.
    `backend` is a free-form label (e.g. 'serverless_query_history') rather
    than an enum, for the same forward-compatibility reason as
    QueryUsage.status.
    """
    backend = CharField(primary_key=True)
    last_seen_ms = BigIntegerField(default=0)

    class Meta:
        table_name = 'ingest_watermark'


# NEW: Function to handle production setup (called in poll_clusters.py)
def initialize_production_db():
    db_instance = SqliteDatabase(DATABASE_FILE_NAME,
             pragmas={
                 'journal_mode': 'wal',  # Vital for avoiding lock conflicts
                 'busy_timeout': 5000,  # Wait 5000ms if DB is locked
                 'synchronous': 'NORMAL',  # Faster/safer for WAL mode
             }
    )

    # Connect and force a checkpoint immediately to clear any "lingering" states
    db_instance.connect()

    """This forces SQLite to take everything in the -wal file and shove
     it into the main .db file. If there was a "ghost" update from 
     a previous process that didn't close properly, 
     this synchronizes the state before end_of_day script starts its work.
    """
    db_instance.execute_sql('PRAGMA wal_checkpoint(FULL);')

    # Bind models to the production instance
    ClusterUptime.bind(db_instance)
    ClusterCumulativeUptime.bind(db_instance)
    ClusterInfo.bind(db_instance)
    QueryUsage.bind(db_instance)
    GroupQuotaState.bind(db_instance)
    GroupDailyUsage.bind(db_instance)
    IngestWatermark.bind(db_instance)
    return db_instance


# --- Setup Function ---

def create_tables(db_instance: SqliteDatabase):
    """Connects to the DB and creates the tables from the models."""

    # Only create tables if they do not already exist
    db_instance.create_tables([
        ClusterUptime, ClusterCumulativeUptime, ClusterInfo,
        QueryUsage, GroupQuotaState, GroupDailyUsage, IngestWatermark,
    ])

def to_datetime(s):
    if s is None:
        return None
    if isinstance(s, datetime.datetime):
        return s
    return datetime.datetime.fromisoformat(s)