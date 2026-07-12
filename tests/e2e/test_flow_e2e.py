"""E2E: `flow` record → save → replay on a real device (§2).

Recording is always-on, so driving the app the normal way fills the session log;
we `flow clear` at the start of each test to isolate it. Self-heal and the
regression exit-1 path are forced deterministically by hand-editing the saved
YAML — a real static test app won't drift a locator or change behaviour on its
own, but the replay machinery must handle both.
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.e2e


def _save(fresh, path: Path) -> dict:
    rc, out, _ = fresh.run("flow", "save", str(path), check=False)
    assert rc == 0 and path.exists(), out
    return yaml.safe_load(path.read_text())


def test_flow_records_saves_and_replays(fresh, app, tmp_path):
    """Explore a flow (navigation + type + assertion), save it, reset, replay green."""
    fresh.run("flow", "clear")
    ref = app.reach_editable(fresh)                 # Android navigates (recorded); iOS is a no-op
    fresh.run("type", ref, app.type_value, "--clear")
    fresh.run("expect", ref, "--value", app.type_value)   # recorded assertion → re-checked on replay

    doc = _save(fresh, tmp_path / "flow.yaml")
    assert doc["platform"] == app.platform and doc["steps"]
    assert any(s["action"] == "expect" for s in doc["steps"])

    fresh.run("reset")
    fresh.run("wait", "--text", app.ready_text, "--timeout", "10")
    rc, data = fresh.run("flow", "replay", str(tmp_path / "flow.yaml"),
                         json_out=True, check=False)
    assert rc == 0, data
    assert data["passed"] == data["total"]


def test_flow_replay_self_heals_when_locator_drifts(fresh, app, tmp_path):
    """A tap whose recorded (by,value) is broken still lands via the captured text."""
    fresh.run("flow", "clear")
    ref = app.ready_ref(fresh)
    fresh.run("tap", ref)                            # a tap on an element with display text
    flow = tmp_path / "heal.yaml"
    doc = _save(fresh, flow)

    step = doc["steps"][0]
    if step["action"] != "tap" or not step["locator"].get("text"):
        pytest.skip("ready element has no captured text to heal by on this platform")
    step["locator"]["by"] = "id"
    step["locator"]["value"] = "no.such.locator/xyz"   # break the primary locator only
    flow.write_text(yaml.safe_dump(doc))

    fresh.run("reset")
    fresh.run("wait", "--text", app.ready_text, "--timeout", "10")
    rc, data = fresh.run("flow", "replay", str(flow), json_out=True, check=False)
    assert rc == 0, data
    assert data["healed"] >= 1                        # it recovered via the captured text


def test_flow_replay_failed_assertion_exits_1(fresh, app, tmp_path):
    """A recorded assertion that no longer holds fails the replay (a regression)."""
    fresh.run("flow", "clear")
    ref = app.ready_ref(fresh)
    fresh.run("expect", ref, "--visible")            # passes now; rewrite it to a false check
    flow = tmp_path / "reg.yaml"
    doc = _save(fresh, flow)

    doc["steps"][0]["matcher"] = {"kind": "text", "expected": "zzz-not-on-screen"}
    doc["steps"][0]["timeout"] = 1                    # don't poll the full default window
    flow.write_text(yaml.safe_dump(doc))

    rc, data = fresh.run("flow", "replay", str(flow), json_out=True, check=False)
    assert rc == 1 and data["failed"] >= 1
