from __future__ import annotations

import datetime
import re

from yutto.utils.console.logger import Logger


class Filter:
    # NOTE(FrankHB): A workaround to https://bugs.python.org/issue31212.
    batch_filter_start_time: datetime.datetime = datetime.datetime(1971, 1, 1)
    batch_filter_end_time: datetime.datetime = datetime.datetime.now() + datetime.timedelta(days=1)

    @staticmethod
    def set_timer(key: str, user_input: str):
        """设置过滤器的时间"""
        timer: datetime.datetime | None = None
        if re.match(r"^\d{4}-\d{2}-\d{2}$", user_input):
            timer = datetime.datetime.strptime(user_input, "%Y-%m-%d")
        elif re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", user_input):
            timer = datetime.datetime.strptime(user_input, "%Y-%m-%d %H:%M:%S")
        else:
            Logger.error(f"稿件过滤参数: {user_input} 看不懂呢┭┮﹏┭┮，不会生效哦")
            return
        setattr(Filter, key, timer)

    @staticmethod
    def verify_timer(timestamp: int) -> bool:
        return Filter.batch_filter_start_time.timestamp() <= timestamp < Filter.batch_filter_end_time.timestamp()
