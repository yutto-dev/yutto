from typing import Any, Optional

from yutto.utils.console.colorful import Color, Style, colored_string
from yutto.utils.console.formatter import get_string_width
from yutto.utils.console.status_bar import StatusBar

_logger_debug: bool = False


def set_logger_debug():
    global _logger_debug
    _logger_debug = True


class Badge:
    def __init__(
        self,
        text: str = "CUSTOM",
        fore: Optional[Color] = None,
        back: Optional[Color] = None,
        style: Optional[list[Style]] = None,
    ):
        self.text: str = text
        self.fore: Optional[Color] = fore
        self.back: Optional[Color] = back
        self.style: Optional[list[Style]] = style

    def __str__(self):
        return colored_string(" {} ".format(self.text), fore=self.fore, back=self.back, style=self.style)

    def __repr__(self):
        return str(self)

    def __len__(self):
        return get_string_width(str(self))

    def __add__(self, other: str) -> str:
        return str(self) + other


WARNING_BADGE = Badge("WARN", fore="yellow")
ERROR_BADGE = Badge("ERROR", fore="red", style=["bold"])
INFO_BADGE = Badge("INFO", fore="bright_blue")
DEBUG_BADGE = Badge("DEBUG", fore="green")


class Logger:
    status = StatusBar

    @classmethod
    def enable_statusbar(cls):
        cls.status.enable()

    @classmethod
    def custom(cls, string: Any, badge: Badge, *print_args: Any, **print_kwargs: Any):
        prefix = badge + " "
        cls.status.clear()
        print(prefix + str(string), *print_args, **print_kwargs)
        cls.status.set_wait()

    @classmethod
    def warning(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom(string, WARNING_BADGE, *print_args, **print_kwargs)

    @classmethod
    def error(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom(string, ERROR_BADGE, *print_args, **print_kwargs)

    @classmethod
    def info(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom(string, INFO_BADGE, *print_args, **print_kwargs)

    @classmethod
    def debug(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        if not _logger_debug:
            return
        Logger.custom(string, DEBUG_BADGE, *print_args, **print_kwargs)

    @classmethod
    def custom_multiline(cls, string: Any, badge: Badge, *print_args: Any, **print_kwargs: Any):
        prefix = badge + " "
        lines = string.split("\n")
        multiline_string = prefix + "\n".join(
            [((" " * get_string_width(prefix)) if i != 0 else "") + line for i, line in enumerate(lines)]
        )
        print(multiline_string, *print_args, **print_kwargs)

    @classmethod
    def warning_multiline(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom_multiline(string, WARNING_BADGE, *print_args, **print_kwargs)

    @classmethod
    def error_multiline(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom_multiline(string, ERROR_BADGE, *print_args, **print_kwargs)

    @classmethod
    def info_multiline(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom_multiline(string, INFO_BADGE, *print_args, **print_kwargs)

    @classmethod
    def debug_multiline(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        if not _logger_debug:
            return
        Logger.custom_multiline(string, INFO_BADGE, *print_args, **print_kwargs)

    @classmethod
    def print(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        print(string, *print_args, **print_kwargs)

    @classmethod
    def is_debug(cls) -> bool:
        return _logger_debug
