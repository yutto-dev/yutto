from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import yutto.downloader.downloader as downloader_module
import yutto.utils.ffmpeg as ffmpeg_module
from yutto.downloader.downloader import merge_video_and_audio
from yutto.exceptions import PostprocessingError
from yutto.utils.ffmpeg import FFmpeg, FFmpegCommandBuilder
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from yutto.types import AudioUrlMeta, DownloaderOptions


def make_ffmpeg(path: str) -> FFmpeg:
    ffmpeg = object.__new__(FFmpeg)
    ffmpeg.path = path
    return ffmpeg


def make_audio() -> AudioUrlMeta:
    return {
        "url": "https://example.com/audio",
        "mirrors": [],
        "codec": "mp4a",
        "width": 0,
        "height": 0,
        "quality": 30280,
    }


def make_merge_options() -> DownloaderOptions:
    return cast(
        "DownloaderOptions",
        {
            "video_save_codec": "copy",
            "audio_save_codec": "copy",
        },
    )


async def merge_audio(output_path: Path, options: DownloaderOptions | None = None) -> None:
    await merge_video_and_audio(
        video=None,
        video_path=output_path.with_name("video.m4s"),
        audio=make_audio(),
        audio_path=output_path.with_name("audio.m4s"),
        cover_data=None,
        cover_path=output_path.with_name("cover.jpg"),
        chapter_info_data=[],
        chapter_info_path=output_path.with_name("chapter.ini"),
        output_path=output_path,
        options=options or make_merge_options(),
    )


def test_video_input_only():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_output("output.mp4")
    excepted_command = ["-i", "input.m4s", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_audio_input_only():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_audio_input("input.aac")
    command_builder.add_output("output.mp4")
    excepted_command = ["-i", "input.aac", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_auto_stream_selection():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    command_builder.add_output("output.mp4")
    excepted_command = ["-i", "input.m4s", "-i", "input.aac", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_manual_stream_selection_select_all():
    command_builder = FFmpegCommandBuilder()
    video_input = command_builder.add_video_input("input.m4s")
    audio_input = command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.use(video_input)
    output.use(audio_input)
    excepted_command = ["-i", "input.m4s", "-i", "input.aac", "-map", "0", "-map", "1", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_manual_stream_selection_select_video_only():
    command_builder = FFmpegCommandBuilder()
    video_input = command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.use(video_input)
    excepted_command = ["-i", "input.m4s", "-i", "input.aac", "-map", "0", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_cover():
    command_builder = FFmpegCommandBuilder()
    video_input = command_builder.add_video_input("input.m4s")
    audio_input = command_builder.add_audio_input("input.aac")
    cover_input = command_builder.add_video_input("cover.jpg")
    output = command_builder.add_output("output.mp4")
    output.use(video_input)
    output.use(audio_input)
    output.use(cover_input)
    output.set_cover(cover_input)
    excepted_command = [
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-i",
        "cover.jpg",
        "-map",
        "0",
        "-map",
        "1",
        "-map",
        "2",
        "-c:v:1",
        "copy",
        "-disposition:v:1",
        "attached_pic",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_cover_reorder():
    command_builder = FFmpegCommandBuilder()
    cover_input = command_builder.add_video_input("cover.jpg")
    video_input = command_builder.add_video_input("input.m4s")
    audio_input = command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.use(cover_input)
    output.use(audio_input)
    output.use(video_input)
    output.set_cover(cover_input)
    excepted_command = [
        "-i",
        "cover.jpg",
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-map",
        "0",
        "-map",
        "2",
        "-map",
        "1",
        "-c:v:0",
        "copy",
        "-disposition:v:0",
        "attached_pic",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_codec():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.set_vcodec("hevc")
    output.set_acodec("copy")
    excepted_command = [
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-vcodec",
        "hevc",
        "-acodec",
        "copy",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_extra_options():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.with_extra_options(["-strict", "unofficial"])
    command_builder.with_extra_options(["-threads", "8"])
    excepted_command = [
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-threads",
        "8",
        "-strict",
        "unofficial",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


@pytest.mark.processor
@as_sync
async def test_ffmpeg_exec_async_preserves_completed_process_output():
    ffmpeg = make_ffmpeg(sys.executable)
    script = "import sys; sys.stdout.buffer.write(b'out'); sys.stderr.buffer.write(b'err'); raise SystemExit(7)"

    result = await ffmpeg.exec_async(["-c", script])

    assert result.args == [sys.executable, "-c", script]
    assert result.returncode == 7
    assert result.stdout == b"out"
    assert result.stderr == b"err"


@pytest.mark.processor
@as_sync
async def test_ffmpeg_exec_async_terminates_and_reaps_on_cancellation(monkeypatch: pytest.MonkeyPatch):
    class FakeProcess:
        def __init__(self):
            self.returncode: int | None = None
            self.communicate_started = asyncio.Event()
            self.terminated = False
            self.waited = False

        async def communicate(self) -> tuple[bytes, bytes]:
            self.communicate_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        async def wait(self) -> int:
            self.waited = True
            assert self.returncode is not None
            return self.returncode

    process = FakeProcess()
    invocation: tuple[tuple[str, ...], dict[str, object]] | None = None

    async def create_subprocess_exec(*cmd: str, **options: object) -> FakeProcess:
        nonlocal invocation
        invocation = cmd, options
        return process

    monkeypatch.setattr(ffmpeg_module.asyncio, "create_subprocess_exec", create_subprocess_exec)
    ffmpeg = make_ffmpeg("ffmpeg-test")
    execution = asyncio.create_task(ffmpeg.exec_async(["-i", "video.m4s"]))
    await process.communicate_started.wait()

    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await execution

    assert invocation == (
        ("ffmpeg-test", "-i", "video.m4s"),
        {
            "stdin": subprocess.DEVNULL,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        },
    )
    assert process.terminated is True
    assert process.waited is True


@pytest.mark.processor
@as_sync
async def test_ffmpeg_exec_async_kills_after_terminate_timeout(monkeypatch: pytest.MonkeyPatch):
    class StubbornProcess:
        def __init__(self):
            self.returncode: int | None = None
            self.communicate_started = asyncio.Event()
            self.terminated = False
            self.killed = False

        async def communicate(self) -> tuple[bytes, bytes]:
            self.communicate_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

        async def wait(self) -> int:
            if self.returncode is None:
                await asyncio.Event().wait()
            assert self.returncode is not None
            return self.returncode

    process = StubbornProcess()

    async def create_subprocess_exec(*cmd: str, **options: object) -> StubbornProcess:
        return process

    monkeypatch.setattr(ffmpeg_module.asyncio, "create_subprocess_exec", create_subprocess_exec)
    monkeypatch.setattr(ffmpeg_module, "_TERMINATE_TIMEOUT_SECONDS", 0)
    execution = asyncio.create_task(make_ffmpeg("ffmpeg-test").exec_async([]))
    await process.communicate_started.wait()

    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await execution

    assert process.terminated is True
    assert process.killed is True


@pytest.mark.processor
@as_sync
async def test_merge_uses_async_ffmpeg_without_changing_success_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    commands: list[list[str]] = []
    infos: list[str] = []
    errors: list[str] = []
    debugs: list[str] = []

    class FakeFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            commands.append(args)
            await asyncio.sleep(0)
            return subprocess.CompletedProcess(args, 0, b"", b"ffmpeg detail")

    monkeypatch.setattr(downloader_module, "FFmpeg", FakeFFmpeg)
    monkeypatch.setattr(downloader_module.Logger, "info", lambda message: infos.append(str(message)))
    monkeypatch.setattr(downloader_module.Logger, "error", lambda message: errors.append(str(message)))
    monkeypatch.setattr(downloader_module.Logger, "debug", lambda message: debugs.append(str(message)))

    output_path = tmp_path / "output.m4a"
    await merge_audio(output_path)

    assert len(commands) == 1
    assert commands[0][-1] == str(output_path)
    assert infos == ["开始合并……", "合并完成！"]
    assert errors == []
    assert debugs == ["ffmpeg detail"]


@pytest.mark.processor
@as_sync
async def test_merge_failure_removes_partial_output_and_is_structured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class FailingFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            return subprocess.CompletedProcess(args, 1, b"", b"ffmpeg detail")

    monkeypatch.setattr(downloader_module, "FFmpeg", FailingFFmpeg)
    output_path = tmp_path / "output.m4a"

    with pytest.raises(PostprocessingError, match="ffmpeg detail") as error:
        await merge_audio(output_path)

    assert error.value.code.value == 20
    assert output_path.exists() is False


@pytest.mark.processor
@as_sync
async def test_merge_cancellation_removes_partial_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    started = asyncio.Event()

    class BlockingFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    infos: list[str] = []
    monkeypatch.setattr(downloader_module, "FFmpeg", BlockingFFmpeg)
    monkeypatch.setattr(downloader_module.Logger, "info", lambda message: infos.append(str(message)))
    output_path = tmp_path / "output.m4a"
    merging = asyncio.create_task(merge_audio(output_path))
    await started.wait()

    merging.cancel()
    with pytest.raises(asyncio.CancelledError):
        await merging

    assert output_path.exists() is False
    assert infos == ["开始合并……"]
