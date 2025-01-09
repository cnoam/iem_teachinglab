
import datetime


def timedelta_to_time_string(td:datetime.timedelta)->str:
    """Converts a datetime.timedelta to a SQLite compatible time string."""
    assert td.days == 0  # the output format does not support days
    total_seconds = int(td.total_seconds())
    s = f"{total_seconds//3600:02d}:{total_seconds//60:02d}:{td.seconds%60:02d}"
    return s


def time_string_to_timedelta(v: str) -> datetime.timedelta:
    t = datetime.datetime.strptime(v,"%H:%M:%S")
    return datetime.timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)

def time_string_to_datetime(v: str) -> datetime.datetime:
    return datetime.datetime.strptime(v,"%Y-%m-%dT%H:%M:%S")

def datetime_to_time_string(v: datetime.datetime) -> str:
    return v.strftime("%Y-%m-%dT%H:%M:%S")

