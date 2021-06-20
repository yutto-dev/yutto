import pytest
import subprocess
import sys

from yutto.__version__ import VERSION as yutto_version

PYTHON = sys.executable


@pytest.mark.e2e
def test_version_e2e():
    p = subprocess.run([PYTHON, "-m", "yutto", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    res = p.stdout.decode()
    assert res.strip().endswith(yutto_version)


@pytest.mark.e2e
@pytest.mark.ci_skip
def test_bangumi_e2e():
    short_bangumi = "https://www.bilibili.com/bangumi/play/ep100367"
    p = subprocess.run(
        [PYTHON, "-m", "yutto", short_bangumi, "-q=16", "-w"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


@pytest.mark.e2e
def test_acg_video_e2e():
    short_acg_video = "https://www.bilibili.com/video/BV1AZ4y147Yg"
    p = subprocess.run(
        [PYTHON, "-m", "yutto", short_acg_video, "-q=16", "-w"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
