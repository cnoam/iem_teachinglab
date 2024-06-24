# test sqlite object->database conversion
import sqlite3
from datetime import timedelta

from pyrecord import Record
from database.db_operations import DB

from sqlite3 import connect, register_converter, register_adapter


class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y
    def __repr__(self):
        return "(%f;%f)" % (self.x, self.y)

def adapt_point(point):
    return ("%f;%f" % (point.x, point.y)).encode('ascii')
def convert_point(s):
    x, y = list(map(float, s.split(b";")))
    return Point(x, y)


# Register the adapter
register_adapter(Point, adapt_point)
# Register the converter
register_converter("point", convert_point)

p = Point(4.0, -3.2)
# 1) Using declared types
con = connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
con.execute("create table test(p point)")
con.execute("insert into test(p) values (?)", (p,))
cur = con.execute("select p from test")
print("with declared types:", cur.fetchone()[0])
con.close()
# 2) Using column names
con = connect(":memory:", detect_types=sqlite3.PARSE_COLNAMES)
con.execute("create table test(p)")
con.execute("insert into test(p) values (?)", (p,))
cur = con.execute('select p as "p [point]" from test')
print("with column names:", cur.fetchone()[0])
con.close()


ClusterData = Record.create_type("ClusterData", "start_time", "uptime", "cumulative", "warning_sent","force_terminated")

class x(ClusterData):
    def adapt(self):
        return (self.start_time, self.uptime, self.cumulative, self.warning_sent, self.force_terminated)
    def convert(self, s):
        start_time, uptime, cumulative, warning_sent, force_terminated = s
        return ClusterData(start_time, uptime, cumulative, warning_sent, force_terminated)



def insert_uptime(id, cluster_data):
    db = DB("test.db")
    db.drop_table("cluster_uptimes")
    db.create_tables()
    db.insert_uptime(id, cluster_data)
    res = DB("test.db").select_data("cluster_uptimes")
    print(res)
    db.close()


if __name__ == "__main__":
    insert_uptime('123', x(timedelta(hours= 1),timedelta(hours=3),timedelta(hours= 7),warning_sent=True, force_terminated=False))
    res = DB("test.db").select_data("cluster_uptimes")
    print(res)
    print(x(res))
