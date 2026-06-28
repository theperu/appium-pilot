"""E2E: read-only inspection commands."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_snapshot_has_refs(fresh):
    assert 'ref="e1"' in fresh.snapshot()


def test_snapshot_raw(fresh):
    rc, out, _ = fresh.run("snapshot", "--raw")
    assert rc == 0 and "<" in out and len(out) > 200


def test_source(fresh):
    rc, out, _ = fresh.run("source")
    assert rc == 0 and "<" in out


def test_screenshot(fresh):
    rc, out, _ = fresh.run("screenshot")
    p = Path(out.strip())
    assert p.exists() and p.suffix == ".png" and p.stat().st_size > 0


def test_screenshot_element(fresh, app):
    ref = app.ready_ref(fresh)
    assert ref
    rc, out, _ = fresh.run("screenshot", ref)
    assert Path(out.strip()).exists()


def test_devices(fresh):
    rc, out, _ = fresh.run("devices")
    assert rc == 0 and out.strip()


def test_list_shows_session(fresh, platform):
    _, data = fresh.run("list", json_out=True)
    assert any(s.get("name") == f"test-{platform}" for s in data["sessions"])
