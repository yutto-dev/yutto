from __future__ import annotations

from pathlib import Path
from typing import TypedDict

SubtitleLineData = TypedDict(
    "SubtitleLineData",
    {
        "content": str,
        "from": int,  # This attribute is a keyword in Python, so it can not convert to class syntax
        "to": int,
    },
)

SubtitleData = list[SubtitleLineData]


class Subtitle:
    """播放列表类"""

    def __init__(self):
        self._text = ""
        self._count = 0

    def write_line(self, string: str):
        self._text += string + "\n"

    @staticmethod
    def time_format(seconds: int):
        ms = int(1000 * (seconds - int(seconds)))
        seconds = int(seconds)
        minutes, sec = seconds // 60, seconds % 60
        hour, min = minutes // 60, minutes % 60
        return f"{hour:02}:{min:02}:{sec:02},{ms:03}"

    def write_subtitle(self, subtitle_line_data: SubtitleLineData) -> None:
        self._count += 1
        self.write_line(str(self._count))
        self.write_line(
            "{} --> {}".format(self.time_format(subtitle_line_data["from"]), self.time_format(subtitle_line_data["to"]))
        )
        self.write_line(subtitle_line_data["content"] + "\n")

    def __str__(self) -> str:
        return self._text


def write_subtitle(subtitle_data: SubtitleData, video_path: Path, lang: str):
    video_path = Path(video_path)
    video_name = video_path.stem
    sub = Subtitle()
    subtitle_path = video_path.with_name(f"{video_name}_{lang}.srt")
    for subline in subtitle_data:
        sub.write_subtitle(subline)
    with subtitle_path.open("w", encoding="utf-8") as f:
        f.write(str(sub))
