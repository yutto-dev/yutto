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
DEPRECATED_BADGE = Badge("DEPRECATED", fore="black", back="yellow")
DEBUG_BADGE = Badge("DEBUG", fore="green")


class Logger:
    status = StatusBar

    @classmethod
    def enable_statusbar(cls):
        # StatusBar 为整个 log 模块中唯一有刷新能力的部分，如果禁用（不启用）可以保证 log 的可读性
        cls.status.enable()
        cls.status.set_snippers(
            [
                "( ´･ω･)",
                "(　´･ω)",
                "( 　´･)",
                "( 　 ´)",
                "(     )",
                "(`　  )",
                "(･`   )",
                "(ω･`　)",
                "(･ω･` )",
                "(´･ω･`)",
            ]
        )

    @classmethod
    def custom(cls, string: Any, badge: Badge, *print_args: Any, **print_kwargs: Any):
        prefix = badge + " "
        cls.status.clear()
        print(prefix + str(string), *print_args, **print_kwargs)
        cls.status.next_tick()

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
    def deprecated_warning(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom(string, DEPRECATED_BADGE, *print_args, **print_kwargs)

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
    def deprecated_warning_multiline(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        Logger.custom_multiline(string, DEPRECATED_BADGE, *print_args, **print_kwargs)

    @classmethod
    def debug_multiline(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        if not _logger_debug:
            return
        Logger.custom_multiline(string, INFO_BADGE, *print_args, **print_kwargs)

    @classmethod
    def print(cls, string: Any, *print_args: Any, **print_kwargs: Any):
        cls.status.clear()
        print(string, *print_args, **print_kwargs)

    @classmethod
    def new_line(cls):
        cls.print("")

    @classmethod
    def is_debug(cls) -> bool:
        return _logger_debug
