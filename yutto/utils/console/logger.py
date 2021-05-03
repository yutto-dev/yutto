from typing import Any, Optional

from yutto.utils.functiontools.singleton import Singleton
from yutto.utils.console.colorful import colored_string, Fore, Back, Style
from yutto.utils.console.formatter import get_string_width

_logger_debug: bool = False


def set_logger_debug():
    global _logger_debug
    _logger_debug = True


class Badge:
    def __init__(
        self,
        text: str = "CUSTOM",
        fore: Optional[Fore] = None,
        back: Optional[Back] = None,
        style: Optional[Style] = None,
    ):
        self.text: str = text
        self.fore: Optional[Fore] = fore
        self.back: Optional[Back] = back
        self.style: Optional[Style] = style

    def __str__(self):
        return colored_string(" {} ".format(self.text), fore=self.fore, back=self.back, style=self.style)

    def __repr__(self):
        return str(self)

    def __len__(self):
        return get_string_width(str(self))

    def __add__(self, other: str) -> str:
        return str(self) + other


WARNING_BADGE = Badge("WARN", fore="black", back="yellow")
ERROR_BADGE = Badge("ERROR", fore="white", back="red")
INFO_BADGE = Badge("INFO", fore="black", back="green")
DEBUG_BADGE = Badge("DEBUG", fore="black", back="blue")


class Logger(metaclass=Singleton):
    @classmethod
    def custom(cls, string: Any, badge: Badge, *print_args: Any, **print_kwargs: Any):
        prefix = badge + " "
        print(prefix + str(string), *print_args, **print_kwargs)

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
