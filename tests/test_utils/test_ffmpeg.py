from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import yutto.utils.ffmpeg as ffmpeg_module
from yutto.core.request import DownloadRequest
from yutto.core.result import ResolvedItem
from yutto.downloader.media_muxer import MediaMuxer
from yutto.downloader.planner import DownloadPlan, DownloadPlanner, should_attach_hvc1_tag
from yutto.exceptions import PostprocessingError, WrongArgumentError
from yutto.types import AId, CId
from yutto.utils.ffmpeg import FFmpeg, FFmpegCommandBuilder
from yutto.utils.functional import Singleton, as_sync

if TYPE_CHECKING:
    from yutto.media.codec import VideoCodec
    from yutto.types import AudioUrlMeta, EpisodeData, VideoUrlMeta


def make_ffmpeg(path: str) -> FFmpeg:
    ffmpeg = object.__new__(FFmpeg)
    ffmpeg.path = path
    return ffmpeg


@pytest.fixture
def reset_ffmpeg_singleton():
    original_path = FFmpeg.FFMPEG_PATH
    Singleton._instances.pop(FFmpeg, None)
    yield
    FFmpeg.FFMPEG_PATH = original_path
    Singleton._instances.pop(FFmpeg, None)


def test_setup_ffmpeg_path_configures_first_instance(
    monkeypatch: pytest.MonkeyPatch,
    reset_ffmpeg_singleton: None,
):
    monkeypatch.setattr(
        ffmpeg_module.subprocess,
        "run",
        lambda args, capture_output: subprocess.CompletedProcess(args, 1),
    )

    FFmpeg.setup_ffmpeg_path("/opt/ffmpeg/ffmpeg")

    assert FFmpeg().path == "/opt/ffmpeg/ffmpeg"


@pytest.mark.parametrize("returncode", [0, 2])
def test_setup_ffmpeg_path_rejects_non_ffmpeg_executable(
    monkeypatch: pytest.MonkeyPatch,
    reset_ffmpeg_singleton: None,
    returncode: int,
):
    monkeypatch.setattr(
        ffmpeg_module.subprocess,
        "run",
        lambda args, capture_output: subprocess.CompletedProcess(args, returncode),
    )

    with pytest.raises(WrongArgumentError, match="请配置正确的 FFmpeg 路径"):
        FFmpeg.setup_ffmpeg_path("not-ffmpeg")

    assert FFmpeg.FFMPEG_PATH == "ffmpeg"


def test_setup_ffmpeg_path_rejects_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
    reset_ffmpeg_singleton: None,
):
    def raise_file_not_found(_args: list[str], capture_output: bool) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError

    monkeypatch.setattr(ffmpeg_module.subprocess, "run", raise_file_not_found)

    with pytest.raises(WrongArgumentError, match="请配置正确的 FFmpeg 路径"):
        FFmpeg.setup_ffmpeg_path("missing-ffmpeg")

    assert FFmpeg.FFMPEG_PATH == "ffmpeg"


def test_ffmpeg_uses_default_path(reset_ffmpeg_singleton: None):
    assert FFmpeg().path == "ffmpeg"


def make_audio() -> AudioUrlMeta:
    return {
        "url": "https://example.com/audio",
        "mirrors": [],
        "codec": "mp4a",
        "width": 0,
        "height": 0,
        "quality": 30280,
    }


def make_video(*, codec: VideoCodec = "hevc", quality: int = 80) -> VideoUrlMeta:
    return cast(
        "VideoUrlMeta",
        {
            "url": "https://example.com/video",
            "mirrors": [],
            "codec": codec,
            "width": 1920,
            "height": 1080,
            "quality": quality,
        },
    )


def make_audio_plan(
    tmp_path: Path,
    *,
    audio_save_codec: str = "copy",
) -> DownloadPlan:
    path = Path("output")
    episode = cast(
        "EpisodeData",
        {
            "info": {
                "listing": ResolvedItem(
                    avid=AId("1"),
                    cid=CId("1"),
                    url="https://www.bilibili.com/video/av1?p=1",
                    name=path.name,
                    title=path.name,
                    cover_url="",
                    planned_path=path,
                ),
                "path": path,
            },
            "videos": [],
            "audios": [make_audio()],
            "subtitles": [],
            "metadata": None,
            "danmaku": {"source_type": None, "save_type": None, "data": []},
            "cover_data": None,
            "chapter_info_data": [],
        },
    )
    request = DownloadRequest.model_validate(
        {
            "source": {"url": "BV1muxer"},
            "resources": {
                "video": False,
                "audio": True,
                "danmaku": False,
                "subtitle": False,
                "metadata": False,
                "cover": False,
                "chapter_info": False,
            },
            "stream": {
                "audio_download_codec": "mp4a",
                "audio_save_codec": audio_save_codec,
            },
            "output": {
                "directory": tmp_path,
                "temporary_directory": tmp_path,
            },
        }
    )
    return DownloadPlanner().plan(episode, request)


@pytest.mark.parametrize(
    ("video", "video_save_codec", "expected"),
    [
        (None, "hevc", False),
        (make_video(quality=126), "hevc", False),
        (make_video(quality=126), "copy", False),
        (make_video(codec="avc"), "hevc", True),
        (make_video(codec="hevc"), "copy", True),
        (make_video(codec="avc"), "copy", False),
    ],
)
def test_should_attach_hvc1_tag(video: VideoUrlMeta | None, video_save_codec: str, expected: bool):
    assert should_attach_hvc1_tag(video, video_save_codec) is expected


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
async def test_media_muxer_uses_async_ffmpeg(tmp_path: Path):
    commands: list[list[str]] = []

    class FakeFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            commands.append(args)
            await asyncio.sleep(0)
            Path(args[-1]).write_bytes(b"merged output")
            return subprocess.CompletedProcess(args, 0, b"", b"ffmpeg detail")

    plan = make_audio_plan(tmp_path, audio_save_codec="mp4a")
    await MediaMuxer(FakeFFmpeg()).mux(plan)

    assert len(commands) == 1
    assert commands[0][-1] == str(plan.paths.output)
    assert commands[0][commands[0].index("-acodec") + 1] == "copy"


@pytest.mark.processor
@as_sync
async def test_merge_success_code_without_output_is_structured_error(
    tmp_path: Path,
):
    class MissingOutputFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            return subprocess.CompletedProcess(args, 0, b"", b"")

    plan = make_audio_plan(tmp_path)

    with pytest.raises(PostprocessingError, match="未生成目标文件") as error:
        await MediaMuxer(MissingOutputFFmpeg()).mux(plan)

    assert error.value.code.value == 20


@pytest.mark.processor
@as_sync
async def test_merge_failure_removes_partial_output_and_is_structured(tmp_path: Path):
    class FailingFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            return subprocess.CompletedProcess(args, 1, b"", b"ffmpeg detail")

    plan = make_audio_plan(tmp_path)

    with pytest.raises(PostprocessingError, match="ffmpeg detail") as error:
        await MediaMuxer(FailingFFmpeg()).mux(plan)

    assert error.value.code.value == 20
    assert plan.paths.output.exists() is False


@pytest.mark.processor
@as_sync
async def test_merge_cancellation_removes_partial_output(tmp_path: Path):
    started = asyncio.Event()

    class BlockingFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            Path(args[-1]).write_bytes(b"partial output")
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    plan = make_audio_plan(tmp_path)
    merging = asyncio.create_task(MediaMuxer(BlockingFFmpeg()).mux(plan))
    await started.wait()

    merging.cancel()
    with pytest.raises(asyncio.CancelledError):
        await merging

    assert plan.paths.output.exists() is False
