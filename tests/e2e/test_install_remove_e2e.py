"""E2E: install/remove an app artifact (closes the previously-untested gap).

Runs on the shared session but restores the app before finishing, so later tests
that reset the app still work.
"""

import pytest

pytestmark = pytest.mark.e2e


def test_remove_then_reinstall(session, app):
    artifact = app.artifact()

    # Uninstall the app under test and confirm it's gone from the screen.
    assert session.run("remove", app.app_id, check=False)[0] == 0
    gone = session.run("wait", "--text", app.ready_text, "--timeout", "3", check=False)[0]
    assert gone != 0, "app content still present after remove"

    # Reinstall the artifact and bring it back to the foreground.
    assert session.run("install", str(artifact), check=False)[0] == 0
    assert session.run("activate", app.app_id, check=False)[0] == 0
    assert session.run("wait", "--text", app.ready_text, "--timeout", "15", check=False)[0] == 0
