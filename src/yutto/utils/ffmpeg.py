from __future__ import annotations

import operator
import os
import re
import subprocess
from functools import cached_property, reduce
from pathlib import Path

from yutto.utils.console.logger import Logger
from yutto.utils.funcutils import Singleton


class FFmpegNotFoundError(Exception):
    def __init__(self):
        super().__init__("请配置正确的 FFmpeg 路径")


class FFmpeg(metaclass=Singleton):
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        try:
            if subprocess.run([ffmpeg_path], capture_output=True).returncode != 1:
                raise FFmpegNotFoundError
        except FileNotFoundError:
            raise FFmpegNotFoundError from None

        self.path = os.path.normpath(ffmpeg_path)

    def exec(self, args: list[str]):
        cmd = [self.path]
        cmd.extend(args)
        Logger.debug(" ".join(cmd))
        # NOTE(aheadlead): FFmpeg 会谜之从 stdin 读取一个字节，这会让调用 yutto 的 shell 脚本踩到坑
        # 这个行为在目前最新的 FFmpeg 6.0 仍然存在
        return subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True)

    @cached_property
    def version(self) -> str:
        output = self.exec(["-version"]).stdout.decode()
        if match_obj := re.match(r"ffmpeg version (?P<version>(\S+)) Copyright", output):
            return match_obj.group("version")
        return "Unknown version"

    @cached_property
    def video_encodecs(self) -> list[str]:
        results: list[str] = []
        output = self.exec(["-codecs"]).stdout.decode()
        for line in output.split("\n"):
            if match_obj := re.match(r"^\s*[D\.]EV[I\.][L\.][S\.] (?P<vcodec>\S+)", line):
                results.append(match_obj.group("vcodec"))
        output = self.exec(["-encoders"]).stdout.decode()
        for line in output.split("\n"):
            if match_obj := re.match(r"^\s*V[F\.][S\.][X\.][B\.][D\.] (?P<encoder>\S+)", line):
                results.append(match_obj.group("encoder"))
        return results

    @cached_property
    def audio_encodecs(self) -> list[str]:
        results: list[str] = []
        output = self.exec(["-codecs"]).stdout.decode()
        for line in output.split("\n"):
            if match_obj := re.match(r"^\s*[D\.]EA[I\.][L\.][S\.] (?P<acodec>\S+)", line):
                results.append(match_obj.group("acodec"))
        output = self.exec(["-encoders"]).stdout.decode()
        for line in output.split("\n"):
            if match_obj := re.match(r"^\s*A[F\.][S\.][X\.][B\.][D\.] (?P<encoder>\S+)", line):
                results.append(match_obj.group("encoder"))
        return results


def concat_commands(commands: list[list[str]]) -> list[str]:
    return reduce(operator.add, commands, list[str]())


class FFmpegInput:
    def __init__(self, path: Path | str, input_id: int, stream_id: int):
        self.path = Path(path)
        self.input_id = input_id
        self.stream_id = stream_id

    def build_select_command(self) -> list[str]:
        return ["-map", str(self.input_id)]

    def build_input_command(self) -> list[str]:
        return ["-i", str(self.path)]

    def __repr__(self):
        return f"FFmpegInput({self.path})"


class FFmpegVideoInput(FFmpegInput): ...


class FFmpegAudioInput(FFmpegInput): ...


class FFmpegMetadataInput(FFmpegInput):
    def build_select_command(self) -> list[str]:
        return ["-map_metadata", str(self.input_id)]


class FFmpegOutput:
    def __init__(self, path: Path | str):
        self.path = path
        self.used_inputs: list[FFmpegInput] = []
        self.vcodec: str | None = None
        self.acodec: str | None = None
        self.cover_input: FFmpegVideoInput | None = None
        self.metadata_input: FFmpegMetadataInput | None = None
        self.extra_commands: list[str] = []

    def use(self, input: FFmpegInput):
        self.used_inputs.append(input)
        return self

    def set_vcodec(self, codec: str):
        self.vcodec = codec
        return self

    def set_acodec(self, codec: str):
        self.acodec = codec
        return self

    def set_cover(self, cover: FFmpegVideoInput):
        self.cover_input = cover
        return self

    def set_metadata(self, metadata: FFmpegMetadataInput):
        self.metadata_input = metadata
        return self

    def with_extra_options(self, command: list[str]):
        self.extra_commands.extend(command)
        return self

    def build(self) -> list[str]:
        selected_inputs = concat_commands([input.build_select_command() for input in self.used_inputs])
        vcodec = ["-vcodec", self.vcodec] if self.vcodec else []
        acodec = ["-acodec", self.acodec] if self.acodec else []
        # Refer to `-disposition` option in https://www.ffmpeg.org/ffmpeg.html#toc-Main-options
        cover_options = (
            [
                f"-c:v:{self.cover_input.stream_id}",
                "copy",
                f"-disposition:v:{self.cover_input.stream_id}",
                "attached_pic",
            ]
            if self.cover_input
            else []
        )
        # Using double dash to make sure that the output file name is not parsed as an option
        # if the output file name starts with a dash
        return selected_inputs + vcodec + acodec + cover_options + self.extra_commands + ["--"] + [str(self.path)]

    def __repr__(self):
        return f"FFmpegOutput({self.path})"


class FFmpegCommandBuilder:
    def __init__(self):
        self.num_inputs = 0
        self.num_video_stream = 0
        self.num_audio_stream = 0
        self.inputs: list[FFmpegInput] = []
        self.outputs: list[FFmpegOutput] = []
        self.extra_commands: list[str] = []

    def add_video_input(self, path: Path | str):
        input = FFmpegVideoInput(path, self.num_inputs, self.num_video_stream)
        self.num_inputs += 1
        self.num_video_stream += 1
        self.inputs.append(input)
        return input

    def add_audio_input(self, path: Path | str):
        input = FFmpegAudioInput(path, self.num_inputs, self.num_audio_stream)
        self.num_inputs += 1
        self.num_audio_stream += 1
        self.inputs.append(input)
        return input

    def add_metadata_input(self, path: Path | str):
        input = FFmpegMetadataInput(path, self.num_inputs, 0)
        self.num_inputs += 1
        self.inputs.append(input)
        return input

    def with_extra_options(self, command: list[str]):
        self.extra_commands.extend(command)
        return self

    def add_output(self, path: Path | str):
        output = FFmpegOutput(path)
        self.outputs.append(output)
        return output

    def build(self):
        input_commands = concat_commands([input.build_input_command() for input in self.inputs])
        output_commands = concat_commands([output.build() for output in self.outputs])
        return input_commands + self.extra_commands + output_commands

    def __repr__(self):
        return "FFmpegCommandBuilder()"
