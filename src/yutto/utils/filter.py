from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from yutto.utils.console.logger import Logger


@dataclass(frozen=True, slots=True)
class PublicationTimeFilter:
    start_time: datetime.datetime
    end_time: datetime.datetime

    @classmethod
    def from_strings(cls, start_time: str | None = None, end_time: str | None = None) -> PublicationTimeFilter:
        start = datetime.datetime(1971, 1, 1)
        end = datetime.datetime.now() + datetime.timedelta(days=1)
        if start_time:
            start = cls._parse(start_time) or start
        if end_time:
            end = cls._parse(end_time) or end
        return cls(start_time=start, end_time=end)

    @staticmethod
    def _parse(user_input: str) -> datetime.datetime | None:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", user_input):
            return datetime.datetime.strptime(user_input, "%Y-%m-%d")
        elif re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", user_input):
            return datetime.datetime.strptime(user_input, "%Y-%m-%d %H:%M:%S")
        Logger.error(f"稿件过滤参数: {user_input} 看不懂呢┭┮﹏┭┮，不会生效哦")
        return None

    def matches(self, timestamp: int) -> bool:
        return self.start_time.timestamp() <= timestamp < self.end_time.timestamp()

    @property
    def start_timestamp(self) -> int:
        return int(self.start_time.timestamp())
