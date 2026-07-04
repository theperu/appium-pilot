"""E2E: tap, text entry, keyboard, and ref error semantics."""

import pytest

pytestmark = pytest.mark.e2e


def test_tap_navigates(fresh, app):
    expect = app.tap_check(fresh)  # performs a tap; returns text expected afterwards
    rc, _, _ = fresh.run("wait", "--text", expect, "--timeout", "8", check=False)
    assert rc == 0, f"expected {expect!r} on screen after tap"


def test_type_and_clear(fresh, app):
    ref = app.reach_editable(fresh)
    assert ref
    fresh.run("type", ref, app.type_value, "--clear")
    assert app.type_value in fresh.snapshot()
    fresh.run("clear", ref)  # re-finds by the stable input locator (the fix)
    assert app.type_value not in fresh.snapshot()


def test_hide_keyboard(fresh, app):
    ref = app.reach_editable(fresh)
    assert ref
    fresh.run("type", ref, app.type_value)
    assert fresh.run("hide-keyboard", check=False)[0] == 0


def test_unknown_ref_exits_2(fresh):
    assert fresh.run("tap", "e999", check=False)[0] == 2


def test_stale_ref_exits_2(fresh, app):
    if app.platform != "android":
        pytest.skip("stale-by-navigation scenario is android-specific here")
    ref = app.ready_ref(fresh)
    assert ref
    fresh.run("tap", ref)               # navigates away; ref's element no longer present
    assert fresh.run("tap", ref, check=False)[0] == 2


# --- richer tap: text / coordinate / long / double (§2.2) ------------------

def test_tap_by_text(fresh, app):
    assert fresh.run("tap", "--text", app.ready_text, check=False)[0] == 0


def test_tap_long(fresh, app):
    ref = app.ready_ref(fresh)
    assert fresh.run("tap", ref, "--long", "--duration", "0.4", check=False)[0] == 0


def test_tap_double(fresh, app):
    ref = app.ready_ref(fresh)
    assert fresh.run("tap", ref, "--double", check=False)[0] == 0


def test_tap_at_coordinate(fresh):
    # A corner tap is harmless; this exercises the coordinate gesture path.
    assert fresh.run("tap", "--at", "1,1", check=False)[0] == 0


def test_tap_requires_exactly_one_target(fresh):
    assert fresh.run("tap", check=False)[0] != 0            # none
    assert fresh.run("tap", "e1", "--at", "1,1", check=False)[0] != 0  # two
