import os
from typing import TypedDict

SubtitleLineData = TypedDict("SubtitleLineData", {"content": str, "from": int, "to": int})


SubtitleData = list[SubtitleLineData]


class Subtitle:
    """ 播放列表类 """

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
        return "{:02}:{:02}:{:02},{}".format(hour, min, sec, ms)

    def write_subtitle(self, subtitle_line_data: SubtitleLineData) -> None:
        self._count += 1
        self.write_line(str(self._count))
        self.write_line(
            "{} --> {}".format(self.time_format(subtitle_line_data["from"]), self.time_format(subtitle_line_data["to"]))
        )
        self.write_line(subtitle_line_data["content"] + "\n")

    def __str__(self) -> str:
        return self._text


def write_subtitle(subtitle_data: SubtitleData, video_path: str, lang: str):
    sub = Subtitle()
    video_path_no_ext = os.path.splitext(video_path)[0]
    subtitle_path = "{}_{}.srt".format(video_path_no_ext, lang)
    for subline in subtitle_data:
        sub.write_subtitle(subline)
    with open(subtitle_path, "w", encoding="utf-8") as f:
        f.write(str(sub))
