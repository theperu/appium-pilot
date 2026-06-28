"""E2E: explicit waits."""

import pytest

pytestmark = pytest.mark.e2e


def test_wait_ref(fresh, app):
    ref = app.ready_ref(fresh)
    assert ref
    assert fresh.run("wait", ref, "--timeout", "8", check=False)[0] == 0


def test_wait_text(fresh, app):
    assert fresh.run("wait", "--text", app.ready_text, "--timeout", "8", check=False)[0] == 0


def test_wait_gone(fresh, app):
    ref = app.disappearing_ref(fresh)
    if not ref:
        pytest.skip("no reliably-disappearing element in this app")
    app.cause_disappear(fresh)
    assert fresh.run("wait", "--gone", ref, "--timeout", "8", check=False)[0] == 0
