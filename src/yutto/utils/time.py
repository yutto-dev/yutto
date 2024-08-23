from __future__ import annotations

import time

TIME_FULL_FMT = "%Y-%m-%d %H:%M:%S"
TIME_DATE_FMT = "%Y-%m-%d"


def get_time_stamp_by_now() -> int:
    return int(time.time())


def get_time_str_by_now(fmt: str = TIME_FULL_FMT):
    time_stamp_now = time.time()
    return get_time_str_by_stamp(time_stamp_now, fmt)


def get_time_str_by_stamp(stamp: float, fmt: str = TIME_FULL_FMT):
    local_time = time.localtime(stamp)
    return time.strftime(fmt, local_time)


def get_time_struct_by_stamp(stamp: float):
    return time.localtime(stamp)
