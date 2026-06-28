"""build_snapshot: layout pruning, kept-node nesting, sequential refs."""

from pathlib import Path

from appium_pilot.snapshot import build_snapshot
from appium_pilot.strategies import get_strategy

FIX = Path(__file__).parent.parent / "fixtures"


def _refs_are_sequential(refmap):
    refs = list(refmap)
    return refs == [f"e{i}" for i in range(1, len(refs) + 1)]


def test_android_pruning_and_refs():
    xml, refmap = build_snapshot((FIX / "android_source.xml").read_text(), get_strategy("android"))
    # Pure layout containers carrying only a resource-id are dropped.
    assert "android:id/content" not in xml
    assert "com.x:id/wrap" not in xml
    # Real content survives: scrollable list, clickable rows, row titles, button, input.
    assert 'text="Views"' in xml and 'text="Text"' in xml
    assert "com.x:id/search" in xml  # the EditText
    assert _refs_are_sequential(refmap)


def test_ios_invisible_dropped_and_window_collapsed():
    xml, refmap = build_snapshot((FIX / "ios_source.xml").read_text(), get_strategy("ios"))
    # visible="false" nodes are dropped outright.
    assert "hidden noise" not in xml
    # The pure-layout Window is collapsed; its children bubble up.
    assert "XCUIElementTypeWindow" not in xml
    assert 'name="IntegerA"' in xml and 'name="IntegerB"' in xml
    assert _refs_are_sequential(refmap)


def test_refs_resolve_to_locators():
    _, refmap = build_snapshot((FIX / "android_source.xml").read_text(), get_strategy("android"))
    # Every ref in the map carries a usable locator.
    assert all(loc.by and loc.value for loc in refmap.values())
