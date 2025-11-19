import pytest
from datetime import date
from peewee import SqliteDatabase

from ..database.db_operations import (
    ClusterUptime,
    ClusterCumulativeUptime,
    BaseModel
)

# Define the isolated in-memory database object
TEST_DB = SqliteDatabase(':memory:')

# --- Pytest Fixture for Database Setup ---

@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    """
        Binds models to a clean in-memory DB for each test function
        and handles connection management.
        """
    # 1. CRITICAL STEP: Temporarily re-bind the models to the isolated TEST_DB
    ClusterUptime._meta.database = TEST_DB
    ClusterCumulativeUptime._meta.database = TEST_DB

    # 2. CONNECT & CREATE on the TEST_DB
    TEST_DB.connect()
    TEST_DB.create_tables([ClusterUptime, ClusterCumulativeUptime])
    with TEST_DB.connection_context():
        yield

    # 3. Teardown
    TEST_DB.drop_tables([ClusterUptime, ClusterCumulativeUptime])
    TEST_DB.close()

    # 4. Restore binding (Safeguard)
    ClusterUptime.bind(None)
    ClusterCumulativeUptime.bind(None)



# --- Test Functions ---

def test_cluster_uptime_crud():
    """
    Tests the basic Create, Read, and Update (CRUD) operations for the
    ClusterUptime model.
    """
    cluster_id = 'test-cluster-002'
    initial_cumulative = 60*60
    new_cumulative =  2*60*60 + 30*60


    # 1. CREATE
    # Use .create() to insert a new record
    new_cluster = ClusterUptime.create(
        id=cluster_id,
        uptime_seconds= 10*60 ,
        cumulative_seconds=initial_cumulative,
        warning_sent=False
    )
    assert new_cluster.id == cluster_id
    assert new_cluster.cumulative_seconds == initial_cumulative

    # 2. READ (Verify creation)
    # Use .get() to retrieve the record
    read_cluster = ClusterUptime.get(ClusterUptime.id == cluster_id)
    assert read_cluster.cumulative_seconds == initial_cumulative
    assert read_cluster.warning_sent is False

    # 3. UPDATE
    # Modify the object and call .save()
    read_cluster.cumulative_seconds = new_cumulative
    read_cluster.warning_sent = True
    read_cluster.save()

    # 4. READ (Verify update)
    updated_cluster = ClusterUptime.get(ClusterUptime.id == cluster_id)
    assert updated_cluster.cumulative_seconds == new_cumulative
    assert updated_cluster.warning_sent is True


def test_cumulative_uptime_creation_and_link():
    """
    Tests the creation of a linked record in ClusterCumulativeUptime.
    """
    cluster_id = 'test-cluster-003'
    today = date.today()
    daily_use_s= 45*60


    # Ensure a ClusterUptime record exists to satisfy the Foreign Key constraint
    parent_cluster = ClusterUptime.create(id=cluster_id)

    # 1. CREATE linked record
    unused_var = ClusterCumulativeUptime.create(
        cluster=parent_cluster, # Peewee automatically uses parent_cluster.id
        date=today,
        daily_use_seconds=daily_use_s
    )

    # 2. READ and assert the foreign key link and data
    read_record = ClusterCumulativeUptime.get(
        (ClusterCumulativeUptime.cluster == parent_cluster) &
        (ClusterCumulativeUptime.date == today)
    )

    assert read_record.cluster.id == cluster_id
    assert read_record.date == today
    assert read_record.daily_use_seconds == daily_use_s