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
    return db_instance


# --- Setup Function ---

def create_tables(db_instance: SqliteDatabase):
    """Connects to the DB and creates the tables from the models."""

    # Only create tables if they do not already exist
    db_instance.create_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])

def to_datetime(s):
    if s is None:
        return None
    if isinstance(s, datetime.datetime):
        return s
    return datetime.datetime.fromisoformat(s)