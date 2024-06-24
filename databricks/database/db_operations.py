import sqlite3
import datetime

#from databricks.resource_manager.cluster_uptime import ClusterData


class DB:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()

    def create_table(self, table_name, column_name):
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} ({column_name} TEXT)
        """
        self.cursor.execute(create_table_query)
        self.conn.commit()

    def drop_table(self, table_name):
        drop_table_query = f"""
        DROP TABLE IF EXISTS {table_name}
        """
        self.cursor.execute(drop_table_query)
        self.conn.commit()

    def insert_data(self, table_name, column_name, value_to_insert):
        insert_query = f"""
        INSERT INTO {table_name} ({column_name}) VALUES (?)
        """
        self.cursor.execute(insert_query, (value_to_insert,))
        self.conn.commit()

    def will_not_work_insert_data(self, table_name,dictionary : dict):
        # https://stackoverflow.com/questions/14108162/python-sqlite3-insert-into-table-valuedictionary-goes-here
        insert_query = f"""
        INSERT INTO {table_name} ({dictionary.keys()}) VALUES (?)
        """
        self.cursor.execute(insert_query, dictionary.values())
        self.conn.commit()

    def select_data(self, table_name):
        select_query = f"""
        SELECT * FROM {table_name}
        """
        self.cursor.execute(select_query)
        result = self.cursor.fetchall()
        return result

    def close(self):
        self.conn.close()

    #---- from here, functions specific to the project
    def create_tables(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS cluster_uptimes (id TEXT UNIQUE NOT NULL, uptime TIME, cumulative TIME, warning_sent BOOLEAN, force_terminated BOOLEAN)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS cluster_cumulative_uptimes (id TEXT UNIQUE NOT NULL, date DATE, daily_use TIME)")
        self.conn.commit()

    def clear_table(self, table_name):
        self.cursor.execute(f"DELETE FROM {table_name}")
        self.conn.commit()

    def __getitem__(self, item):
        self.cursor.execute(f"SELECT * FROM cluster_uptimes WHERE id = {item}")
        result = self.cursor.fetchone()
        return result   # returns a tuple

    def __len__(self):
        self.cursor.execute("SELECT COUNT(*) FROM cluster_uptimes")
        result = self.cursor.fetchone()
        return result[0]

    def __contains__(self, item):
        self.cursor.execute(f"SELECT * FROM cluster_uptimes WHERE id = {item}")
        result = self.cursor.fetchone()
        return result is not None

    def insert_uptime(self, id, cluster_data):
        # not sure how to format the timedelta object, so use GPT's advice
        uptime = datetime.datetime(1900,1,1) + cluster_data.uptime
        cumulative = datetime.datetime(1900,1,1) + cluster_data.cumulative
        self.cursor.execute("INSERT INTO cluster_uptimes (id, uptime, cumulative, warning_sent, force_terminated) VALUES (?,?,?,?,?)",
                            (id,
                                uptime.strftime('%H:%M:%S'),
                                cumulative.strftime('%H:%M:%S'),
                                cluster_data.warning_sent,
                                cluster_data.force_terminated))
        self.conn.commit()

    def update_record(self, id_ : str, x):
        cmd = """UPDATE cluster_uptimes
            SET 
                uptime = ?, 
                cumulative = ?, 
                warning_sent = ?, 
                force_terminated = ?
            WHERE
                id = ?;"""
        self.cursor.execute(cmd, (x.uptime, x.cumulative, x.warning_sent, x.force_terminated, id_))


if __name__ == "__main__":
    db = DB("my_database.db")
    db.create_table("my_table", column_name="value")
    db.insert_data("my_table", column_name="value", value_to_insert="Hello, world22!")
    result = db.select_data("my_table")
    print(result)
    db.close()
