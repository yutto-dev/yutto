from __future__ import annotations


class StatusBar:
    _DEFAULT_KEY = "__status__"
    _enabled = False
    tip = ""
    _snippers = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _count = 0
    _lines: dict[str, str] = {}
    _rendered_line_count = 0

    @classmethod
    def enable(cls):
        cls._enabled = True

    @classmethod
    def disable(cls):
        cls.reset()
        cls._enabled = False

    @classmethod
    def set_snippers(cls, snippers: list[str]):
        cls._snippers = snippers

    @classmethod
    def clear(cls):
        if not cls._enabled or cls._rendered_line_count == 0:
            return
        for index in range(cls._rendered_line_count):
            print("\r\x1b[2K", end="")
            if index < cls._rendered_line_count - 1:
                print("\x1b[1A", end="")
        cls._rendered_line_count = 0

    @classmethod
    def redraw(cls):
        if not cls._enabled:
            return
        cls.clear()
        lines = tuple(cls._lines.values())
        for index, line in enumerate(lines):
            print(line, end="\n" if index < len(lines) - 1 else "\r")
        cls._rendered_line_count = len(lines)

    @classmethod
    def set(cls, text: str):
        cls.set_line(cls._DEFAULT_KEY, text)

    @classmethod
    def set_line(cls, key: str, text: str):
        if not key:
            raise ValueError("status line key must not be empty")
        if not cls._enabled:
            return
        if key != cls._DEFAULT_KEY:
            cls._lines.pop(cls._DEFAULT_KEY, None)
        cls._lines[key] = text
        cls.redraw()

    @classmethod
    def remove_line(cls, key: str):
        if not cls._enabled:
            return
        cls._lines.pop(key, None)
        cls.redraw()

    @classmethod
    def reset(cls):
        cls.clear()
        cls._lines.clear()

    @classmethod
    def set_tip(cls, tip: str):
        cls.tip = tip

    @classmethod
    def next_tick(cls):
        if any(key != cls._DEFAULT_KEY for key in cls._lines):
            cls.redraw()
            return
        cls.set(cls._snippers[cls._count] + " " + cls.tip)
        cls._count += 1
        cls._count %= len(cls._snippers)
