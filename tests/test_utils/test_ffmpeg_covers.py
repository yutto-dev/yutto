from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from tests.test_utils.test_ffmpeg import make_audio_plan, make_ffmpeg, make_video
from yutto.downloader.media_muxer import MediaMuxer
from yutto.downloader.planner import freeze_video_stream
from yutto.utils.ffmpeg import FFmpegCommandBuilder
from yutto.utils.functional import as_sync

if TYPE_CHECKING:
    from pathlib import Path

    from yutto.downloader.planner import DownloadPlan


def make_cover_plan(tmp_path: Path) -> DownloadPlan:
    plan = make_audio_plan(tmp_path)
    return replace(
        plan,
        paths=replace(plan.paths, output=tmp_path / "output.mp4"),
        video=freeze_video_stream(make_video(codec="avc"), 0),
        video_save_codec="copy",
        resources=replace(plan.resources, has_cover=True),
    )


@pytest.mark.parametrize(
    ("suffix", "content", "codec"),
    [
        (".jpg", b"\xff\xd8\xff\xe0JPEG", "copy"),
        (".png", b"\xff\xd8\xff\xe1JPEG", "copy"),
        (".jpg", b"\x89PNG\r\n\x1a\n", "png"),
        (".png", b"\x89PNG\r\n\x1a\n", "png"),
    ],
)
@as_sync
async def test_cover_codec_uses_content_not_suffix(tmp_path: Path, suffix: str, content: bytes, codec: str):
    plan = make_cover_plan(tmp_path)
    plan = replace(plan, paths=replace(plan.paths, cover=tmp_path / f"cover{suffix}"))
    plan.paths.cover.write_bytes(content)
    commands: list[list[str]] = []

    class FakeFFmpeg:
        async def exec_async(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
            commands.append(args)
            plan.paths.output.touch()
            return subprocess.CompletedProcess(args, 0, b"", b"")

    await MediaMuxer(FakeFFmpeg()).mux(plan)

    command = commands[0]
    assert command[command.index("-c:v:1") + 1] == codec
    assert ("-filter:v:1" in command) is (codec == "png")
    assert command[command.index("-vcodec") + 1] == "copy"
    assert command[command.index("-acodec") + 1] == "copy"


@pytest.mark.parametrize("cover_first", [False, True])
def test_cover_filter_is_scoped_and_does_not_limit_output_frames(cover_first: bool):
    builder = FFmpegCommandBuilder()
    if cover_first:
        cover = builder.add_video_input("cover.jpg")
        video = builder.add_video_input("video.m4s")
    else:
        video = builder.add_video_input("video.m4s")
        cover = builder.add_video_input("cover.jpg")
    output = builder.add_output("output.mp4")
    for input in builder.inputs:
        output.use(input)
    output.set_vcodec("hevc").set_cover(cover, codec="png")

    command = builder.build()

    assert command[command.index(f"-c:v:{cover.stream_id}") + 1] == "png"
    assert command[command.index(f"-filter:v:{cover.stream_id}") + 1] == "trim=end_frame=1"
    assert f"-filter:v:{video.stream_id}" not in command
    assert not any(option.startswith("-frames") for option in command)


def run_tool(tool: str, *args: str) -> bytes:
    result = subprocess.run([tool, *args], stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


@pytest.fixture(scope="module")
def cover_media(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str, Path]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("FFmpeg and ffprobe are required for local cover muxing tests")
    directory = tmp_path_factory.mktemp("cover-media")
    run_tool(
        ffmpeg,
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=s=64x64:r=5:d=2",
        "-c:v",
        "mpeg4",
        "-bf",
        "2",
        str(directory / "video.mp4"),
    )
    run_tool(
        ffmpeg,
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=2",
        "-c:a",
        "aac",
        str(directory / "audio.m4a"),
    )
    for name, codec, frames, muxer in [
        ("png.jpg", "png", "1", "image2"),
        ("apng.jpg", "apng", "2", "apng"),
        ("jpeg.jpg", "mjpeg", "1", "image2"),
    ]:
        run_tool(
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=s=120x90:r=2:d=1",
            "-frames:v",
            frames,
            "-c:v",
            codec,
            "-f",
            muxer,
            str(directory / name),
        )
    shutil.copyfile(directory / "jpeg.jpg", directory / "jpeg.png")
    return ffmpeg, ffprobe, directory


@pytest.mark.e2e
@pytest.mark.parametrize("container", ["mp4", "mkv"])
@pytest.mark.parametrize("cover_name", ["png.jpg", "apng.jpg", "jpeg.jpg", "jpeg.png"])
@pytest.mark.parametrize("video_save_codec", ["copy", "mpeg4"], ids=["main-copy", "main-transcode"])
@as_sync
async def test_mux_preserves_cover_and_complete_media(
    tmp_path: Path, cover_media: tuple[str, str, Path], container: str, cover_name: str, video_save_codec: str
):
    ffmpeg, ffprobe, media = cover_media
    plan = make_cover_plan(tmp_path)
    plan = replace(
        plan,
        video_save_codec=video_save_codec,
        paths=replace(plan.paths, output=tmp_path / f"output.{container}"),
    )
    shutil.copyfile(media / "video.mp4", plan.paths.video)
    shutil.copyfile(media / "audio.m4a", plan.paths.audio)
    shutil.copyfile(media / cover_name, plan.paths.cover)

    def probe(path: Path):
        return json.loads(
            run_tool(ffprobe, "-v", "error", "-count_packets", "-show_streams", "-of", "json", str(path))
        )["streams"]

    source_video = probe(plan.paths.video)[0]
    source_audio = probe(plan.paths.audio)[0]
    # A genuinely animated PNG must reach FFmpeg as APNG despite the .jpg suffix.
    if cover_name == "apng.jpg":
        assert probe(plan.paths.cover)[0]["codec_name"] == "apng"

    await MediaMuxer(make_ffmpeg(ffmpeg)).mux(plan)

    video, audio, cover = probe(plan.paths.output)
    assert video["codec_name"] == source_video["codec_name"]
    assert audio["codec_name"] == source_audio["codec_name"]
    assert video["nb_read_packets"] == source_video["nb_read_packets"]
    assert audio["nb_read_packets"] == source_audio["nb_read_packets"]
    assert cover["codec_name"] == ("mjpeg" if cover_name.startswith("jpeg") else "png")
    assert (cover["width"], cover["height"]) == (120, 90)
    assert cover["nb_read_packets"] == "1"
    # Matroska retains an image video track, not MP4's attached_pic disposition.
    if container == "mp4":
        assert cover["disposition"]["attached_pic"] == 1
        assert float(video["duration"]) == pytest.approx(float(source_video["duration"]))
        assert float(audio["duration"]) == pytest.approx(float(source_audio["duration"]))

    extracted = run_tool(
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(plan.paths.output),
        "-map",
        "0:v:1",
        "-c",
        "copy",
        "-f",
        "image2pipe",
        "-",
    )
    if cover_name.startswith("jpeg"):
        assert extracted == plan.paths.cover.read_bytes()
    else:
        extracted_path = tmp_path / "extracted.png"
        extracted_path.write_bytes(extracted)

        def first_frame(path: Path) -> bytes:
            return run_tool(
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "-",
            )

        assert first_frame(extracted_path) == first_frame(plan.paths.cover)
