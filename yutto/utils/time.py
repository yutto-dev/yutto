import datetime
import time

TIME_FMT = "%Y-%m-%d %H:%M:%S"


def get_time_str_by_now():
    now = datetime.datetime.now()
    return now.strftime(TIME_FMT)


def get_time_str_by_stamp(stamp):
    local_time = time.localtime(stamp)
    return time.strftime(TIME_FMT, local_time)
