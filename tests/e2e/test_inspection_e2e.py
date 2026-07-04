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


# --- get: live element state without a re-snapshot (§2.3) ------------------

def test_get_reflects_typed_text(fresh, app):
    ref = app.reach_editable(fresh)
    fresh.run("type", ref, app.type_value, "--clear")
    rc, out, _ = fresh.run("get", ref)
    assert rc == 0 and app.type_value in out


def test_get_single_attribute(fresh, app):
    ref = app.ready_ref(fresh)
    rc, out, _ = fresh.run("get", ref, "enabled")
    assert rc == 0 and "true" in out.lower()


# --- snapshot --bounds: opt-in pixel centers (§2.5) ------------------------

def test_snapshot_bounds_adds_center(fresh):
    withb = fresh.run("snapshot", "--bounds")[1]
    assert ' at="' in withb
    # Plain snapshot stays lean — no centers.
    assert ' at="' not in fresh.snapshot()


def test_bounds_center_is_tappable(fresh):
    import re
    out = fresh.run("snapshot", "--bounds")[1]
    m = re.search(r'at="(\d+),(\d+)"', out)
    assert m, "no center emitted"
    assert fresh.run("tap", "--at", f"{m.group(1)},{m.group(2)}", check=False)[0] == 0
