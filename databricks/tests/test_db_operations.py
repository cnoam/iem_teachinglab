from unittest import TestCase
from databricks.database.db_operations import DB

# create a test fixture for the pytest


class TestDB(TestCase):
    def setUp(self):
        self.db = DB("test.db")
        #self.db.drop_table("cluster_uptimes")
        self.db.create_tables()

    def tearDown(self):
        self.db.close() # close the connection to the database

    def test_insert_data(self):
        self.db.drop_table("cluster_uptimes")
        self.db.insert_data("cluster_uptimes", "id", "123")
        self.db.insert_data("cluster_uptimes", "id", "4")
        self.db.insert_data("cluster_uptimes", "id", "123")
        self.db.insert_data("cluster_uptimes", "id", "4")
        self.db.insert_data("cluster_uptimes", "id", "4")
        results = self.db.select_data("cluster_uptimes")



    def test_create_tables(self):
        self.db.cursor.execute("DROP TABLE IF EXISTS cluster_uptimes")
        self.db.cursor.execute("DROP TABLE IF EXISTS cluster_cumulative_uptimes")
        self.db.create_tables()
        results = self.db.select_data("cluster_uptimes")
        self.assertEqual(results, [])
