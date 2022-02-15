import time

TIME_FMT = "%Y-%m-%d %H:%M:%S"


def get_time_str_by_now(fmt: str = TIME_FMT):
    time_stamp_now = time.time()
    return get_time_str_by_stamp(time_stamp_now, fmt)


def get_time_str_by_stamp(stamp: float, fmt: str = TIME_FMT):
    local_time = time.localtime(stamp)
    return time.strftime(fmt, local_time)
