"""E2E: system alert / permission dialog handling."""

import pytest

pytestmark = pytest.mark.e2e


def test_alert_absent_exits_2(fresh):
    # No alert on the ready screen → clean, actionable exit code 2.
    assert fresh.run("alert", check=False)[0] == 2


def test_alert_read_and_accept(fresh, app):
    expected = app.show_alert(fresh)
    if not expected:
        pytest.skip("no alert trigger for this app")
    rc, out, _ = fresh.run("alert")
    assert rc == 0 and expected.lower() in out.lower()
    assert fresh.run("alert", "accept", check=False)[0] == 0
    # Once accepted, the alert is gone.
    assert fresh.run("alert", check=False)[0] == 2
