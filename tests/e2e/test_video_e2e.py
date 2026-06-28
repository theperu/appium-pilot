"""E2E: screen recording produces a real mp4."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_video_record(fresh):
    assert fresh.run("video-start", check=False)[0] == 0
    fresh.run("swipe", "up", check=False)
    rc, out, _ = fresh.run("video-stop")
    path = Path(out.strip())
    assert rc == 0
    assert path.suffix == ".mp4" and path.exists() and path.stat().st_size > 0


def test_video_stop_without_start_errors(fresh):
    # nothing recording -> clean nonzero, no traceback
    assert fresh.run("video-stop", check=False)[0] != 0
