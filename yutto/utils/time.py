import time

TIME_FMT = "%Y-%m-%d %H:%M:%S"


def get_time_str_by_now():
    time_stamp_now = time.time()
    return get_time_str_by_stamp(time_stamp_now)


def get_time_str_by_stamp(stamp: float):
    local_time = time.localtime(stamp)
    return time.strftime(TIME_FMT, local_time)
