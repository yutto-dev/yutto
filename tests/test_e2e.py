from __future__ import annotations

import subprocess
import sys

import pytest

from yutto.__version__ import VERSION as yutto_version

from .conftest import TEST_DIR

PYTHON = sys.executable


@pytest.mark.e2e
def test_version_e2e():
    p = subprocess.run([PYTHON, "-m", "yutto", "-v"], capture_output=True, check=True)
    res = p.stdout.decode()
    assert res.strip().endswith(yutto_version)


@pytest.mark.e2e
@pytest.mark.ci_skip
def test_bangumi_e2e():
    short_bangumi = "https://www.bilibili.com/bangumi/play/ep100367"
    subprocess.run(
        [PYTHON, "-m", "yutto", short_bangumi, f"-d={TEST_DIR}", "-q=16", "-w"],
        capture_output=True,
        check=True,
    )


@pytest.mark.e2e
def test_ugc_video_e2e():
    short_ugc_video = "https://www.bilibili.com/video/BV1AZ4y147Yg"
    subprocess.run(
        [PYTHON, "-m", "yutto", short_ugc_video, f"-d={TEST_DIR}", "-q=16", "-w"],
        capture_output=True,
        check=True,
    )
