"""E2E: app lifecycle (background/terminate/activate/reset)."""

import pytest

pytestmark = pytest.mark.e2e


def test_background(fresh):
    assert fresh.run("background", "1", check=False)[0] == 0


def test_terminate_then_activate(fresh, app):
    assert fresh.run("terminate", check=False)[0] == 0      # uses the session's app id
    assert fresh.run("activate", check=False)[0] == 0
    assert fresh.run("wait", "--text", app.ready_text, "--timeout", "10", check=False)[0] == 0


def test_reset(fresh, app):
    assert fresh.run("reset", check=False)[0] == 0
    assert fresh.run("wait", "--text", app.ready_text, "--timeout", "10", check=False)[0] == 0


def test_quoted_cap_persisted_as_string(session, platform):
    # The --cap force-string escape hatch: open_args passes pilotProbe="17";
    # it must reach the live session as the string "17", not int 17.
    import json

    from appium_pilot import config
    caps = json.loads(config.session_file(f"test-{platform}").read_text())["caps"]
    assert caps.get("appium:pilotProbe") == "17"
