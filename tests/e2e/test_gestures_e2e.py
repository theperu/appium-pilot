"""E2E: swipe and scroll."""

import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
def test_swipe_directions(fresh, direction):
    assert fresh.run("swipe", direction, check=False)[0] == 0


def test_swipe_coords(fresh):
    assert fresh.run("swipe", "coords", "200", "600", "200", "300", check=False)[0] == 0


def test_scroll_ref(fresh, app):
    ref = app.ready_ref(fresh)
    assert ref
    assert fresh.run("scroll", ref, check=False)[0] == 0


def test_scroll_to_text(fresh, app):
    assert fresh.run("scroll", "--to", app.scroll_target, check=False)[0] == 0
