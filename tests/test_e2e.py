from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from yutto.__version__ import VERSION as yutto_version

if TYPE_CHECKING:
    from pathlib import Path

PYTHON = sys.executable
pytestmark = pytest.mark.e2e


def test_version_e2e():
    p = subprocess.run([PYTHON, "-m", "yutto", "-v"], capture_output=True, check=True, timeout=30)
    assert p.stdout.decode().strip().endswith(yutto_version)


@pytest.mark.ci_skip
@pytest.mark.parametrize(
    ("url", "batch_file"),
    [
        pytest.param("https://www.bilibili.com/bangumi/play/ep100367", False, id="bangumi"),
        pytest.param("https://www.bilibili.com/video/BV1AZ4y147Yg", False, id="ugc"),
        pytest.param("https://www.bilibili.com/video/BV1AZ4y147Yg", True, id="batch-file"),
    ],
)
def test_download_e2e(tmp_path: Path, url: str, batch_file: bool):
    config = tmp_path / "yutto.toml"
    config.write_text("")
    output = tmp_path / "downloads"
    if batch_file:
        source = tmp_path / "batch.txt"
        source.write_text(f'{url} --batch -p $ --no-danmaku --vcodec="hevc:copy"\n')
        url = str(source)
    result = subprocess.run(
        [
            PYTHON,
            "-m",
            "yutto",
            url,
            "--config",
            str(config),
            "--auth-file",
            str(tmp_path / "auth.toml"),
            "-d",
            str(output),
            "-q=16",
            "-w",
            "--no-progress",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    media_files = [path for path in output.rglob("*") if path.suffix in {".mp4", ".mkv", ".mov"}]
    assert len(media_files) == 1, result.stdout + result.stderr
    media = media_files[0]
    assert media.stat().st_size > 0
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(media)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    info = json.loads(probe.stdout)
    assert {stream["codec_type"] for stream in info["streams"]} >= {"video", "audio"}
    assert float(info["format"]["duration"]) > 0
