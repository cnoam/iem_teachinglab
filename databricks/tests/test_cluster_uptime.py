from unittest import TestCase
from databricks.resource_manager.cluster_uptime import update_cumulative_uptime
from databricks.database.db_operations import DB


class Test(TestCase):

    def setUp(self):
        self.db = DB("test.db")
        self.db.create_tables()

    def tearDown(self):
        self.db.close()

    def test_update_cumulative_uptime(self):
        update_cumulative_uptime({'driver': {'start_timestamp': 1610000000}, 'cluster_id': '123'}, self.db)
        result = self.db.select_data("cluster_uptimes")
        self.assertEqual(result, [('123', '0:00:00', '0:00:00', 0, 0)])

