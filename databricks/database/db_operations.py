import datetime
import os

from peewee import *

DATABASE_FILE_NAME = 'cluster_uptimes.db'


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
    id = CharField(primary_key=True)

    # Stores the timestamp (seconds since epoch) when the cluster last started.
    # Used for calculating the live 'uptime'. Nullable if the cluster is off.
    start_timestamp = FloatField(null=True)

    # Current uptime of the actively running cycle (in seconds)
    uptime_seconds = FloatField(default=0.0)

    # Total accumulated uptime from all previous cycles (in seconds)
    cumulative_seconds = FloatField(default=0.0)

    warning_sent = BooleanField(default=False)
    force_terminated = BooleanField(default=False)

    #class Meta:
    #    table_name = 'cluster_uptimes'


class ClusterCumulativeUptime(BaseModel):
    """
    Maps to the 'cluster_cumulative_uptimes' table.
    Links daily usage back to a specific cluster.
    """
    # Foreign key link to the ClusterUptime table
    cluster = ForeignKeyField(ClusterUptime, backref='daily_records')

    # Date of the daily use
    date = DateField(default=datetime.date.today)

    # Storing daily usage duration
    daily_use_seconds = FloatField(default=0.0)

    class Meta:
        # Ensures that a cluster can only have one daily use record per date
        indexes = (
            (('cluster', 'date'), True),
        )


# NEW: Function to handle production setup (called in poll_clusters.py)
def initialize_production_db():
    #print(f"DEBUG: Database file is located at: {os.path.abspath(DATABASE_FILE_NAME)}")
    db_instance = SqliteDatabase(DATABASE_FILE_NAME)

    # Bind models to the production instance
    ClusterUptime.bind(db_instance)
    ClusterCumulativeUptime.bind(db_instance)
    return db_instance


# --- Setup Function ---

def create_tables(db_instance: SqliteDatabase):
    """Connects to the DB and creates the tables from the models."""

    # Only create tables if they do not already exist
    db_instance.create_tables([ClusterUptime, ClusterCumulativeUptime])
