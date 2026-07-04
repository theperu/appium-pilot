"""build_snapshot: layout pruning, kept-node nesting, sequential refs."""

import xml.etree.ElementTree as ET
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
    assert 'id="wrap"' not in xml
    # Real content survives: scrollable list, clickable rows, row titles, button, input.
    assert 'text="Views"' in xml and 'text="Text"' in xml
    assert 'id="search"' in xml  # the EditText (resource-id shown package-stripped)
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


def test_android_tags_shortened():
    xml, _ = build_snapshot((FIX / "android_source.xml").read_text(), get_strategy("android"))
    # Emitted tags drop the package path; the agent reads <EditText>, not FQCN.
    assert "<RecyclerView" in xml and "<EditText" in xml and "<ImageButton" in xml
    assert "android.widget" not in xml and "androidx.recyclerview" not in xml


def test_android_shortened_tag_does_not_corrupt_xpath_locator():
    # A bare interactive node with no id/text/desc falls to the path xpath; the
    # emitted tag is shortened, but that xpath must keep the full class name.
    src = "<hierarchy><android.widget.Button/></hierarchy>"
    xml, refmap = build_snapshot(src, get_strategy("android"))
    assert "<Button" in xml and "android.widget" not in xml
    (loc,) = refmap.values()
    assert loc.by == "xpath" and "android.widget.Button" in loc.value


def test_ios_tags_shortened():
    xml, _ = build_snapshot((FIX / "ios_source.xml").read_text(), get_strategy("ios"))
    assert "<Button" in xml and "<TextField" in xml and "<SearchField" in xml
    assert "XCUIElementType" not in xml


def test_ios_label_dropped_when_equal_to_name_kept_when_different():
    xml, _ = build_snapshot((FIX / "ios_source.xml").read_text(), get_strategy("ios"))
    # IntegerA has name == label -> the duplicate label is dropped.
    assert 'name="IntegerA"' in xml
    assert 'label="IntegerA"' not in xml
    # The button has name="Query" label="Clear" -> both are meaningful, both kept.
    assert 'label="Clear"' in xml


def test_android_clickable_row_folds_single_text_child():
    xml, refmap = build_snapshot((FIX / "android_source.xml").read_text(), get_strategy("android"))
    # Each clickable row wrapping one TextView collapses to a single node...
    assert "<TextView" not in xml
    assert '<LinearLayout ref="e2" id="row" clickable="true" text="Views"/>' in xml
    # ...whose ref resolves via the (text-bearing) child's locator.
    assert "Views" in refmap["e2"].value
    assert _refs_are_sequential(refmap)


def test_android_fold_skips_interactive_children():
    src = (
        "<hierarchy>"
        '<android.widget.LinearLayout resource-id="com.x:id/row" clickable="true">'
        '<android.widget.EditText resource-id="com.x:id/field" text="hi"/>'
        "</android.widget.LinearLayout>"
        "</hierarchy>"
    )
    xml, _ = build_snapshot(src, get_strategy("android"))
    # An input is interactive in its own right — never folded away.
    assert "<EditText" in xml


def test_ios_cell_folds_single_static_text():
    src = (
        '<XCUIElementTypeApplication name="App" visible="true">'
        '<XCUIElementTypeCell visible="true">'
        '<XCUIElementTypeStaticText label="Settings" visible="true"/>'
        "</XCUIElementTypeCell>"
        "</XCUIElementTypeApplication>"
    )
    xml, refmap = build_snapshot(src, get_strategy("ios"))
    assert "<StaticText" not in xml
    assert '<Cell ref="e2" label="Settings"/>' in xml
    assert "Settings" in refmap["e2"].value
    assert _refs_are_sequential(refmap)


def test_ios_button_drops_duplicate_label_child_keeps_own_locator():
    src = (
        '<XCUIElementTypeApplication name="App" visible="true">'
        '<XCUIElementTypeButton name="submit" label="Submit" visible="true">'
        '<XCUIElementTypeStaticText label="Submit" visible="true"/>'
        "</XCUIElementTypeButton>"
        "</XCUIElementTypeApplication>"
    )
    xml, refmap = build_snapshot(src, get_strategy("ios"))
    # The duplicated child label vanishes; the button keeps its strong name locator.
    assert xml.count("Submit") == 1
    assert "submit" in refmap["e2"].value
    assert _refs_are_sequential(refmap)


# --- locator dedupe (§3.1) -------------------------------------------------

def _resolves_uniquely(source: str, xpath: str) -> bool:
    """Does `xpath` match exactly one element in `source`?

    The dedupe fallback is only correct if each rewritten locator uniquely
    identifies its element live; asserting the strings merely *differ* would
    pass even for a malformed or non-unique xpath. ElementTree resolves the
    absolute indexed path (a subset of XPath 1.0 the device driver also
    supports) so we can prove uniqueness device-free.
    """
    root = ET.fromstring(source)
    assert xpath.startswith("/" + root.tag), xpath  # absolute path from the root
    relative = "." + xpath[len("/" + root.tag):]
    return len(root.findall(relative)) == 1


def test_duplicate_rows_get_distinct_xpath_locators():
    # Two rows with identical id+text produce the same best_locator; the dedupe
    # pass must fall back to each node's unique indexed xpath so acting on a ref
    # never fails "ambiguous" at action time.
    src = (
        "<hierarchy>"
        '<android.widget.LinearLayout resource-id="com.x:id/row" clickable="true">'
        '<android.widget.TextView resource-id="android:id/title" text="Item"/>'
        "</android.widget.LinearLayout>"
        '<android.widget.LinearLayout resource-id="com.x:id/row" clickable="true">'
        '<android.widget.TextView resource-id="android:id/title" text="Item"/>'
        "</android.widget.LinearLayout>"
        "</hierarchy>"
    )
    xml, refmap = build_snapshot(src, get_strategy("android"))
    assert len(refmap) == 2
    pairs = [(loc.by, loc.value) for loc in refmap.values()]
    assert len(set(pairs)) == 2, f"locators still collide: {pairs}"
    assert all(loc.by == "xpath" for loc in refmap.values())
    # Each fallback xpath must resolve to exactly one live element — the actual
    # correctness claim, not just that the two strings differ.
    assert all(_resolves_uniquely(src, loc.value) for loc in refmap.values())
    # Display text survives for error messages.
    assert all(loc.text == "Item" for loc in refmap.values())
    assert _refs_are_sequential(refmap)


def test_non_colliding_locators_are_left_untouched():
    # Distinct labels must keep their strong (non-xpath) locators.
    xml, refmap = build_snapshot((FIX / "android_source.xml").read_text(), get_strategy("android"))
    non_xpath = [loc for loc in refmap.values() if loc.by != "xpath"]
    assert non_xpath, "dedupe should not have downgraded every locator to xpath"


# --- snapshot --bounds (§2.5) ----------------------------------------------

def test_android_bounds_emits_center_only_when_requested():
    src = ('<hierarchy><android.widget.Button resource-id="com.x:id/b" '
           'text="OK" bounds="[10,20][110,60]"/></hierarchy>')
    plain, _ = build_snapshot(src, get_strategy("android"))
    assert " at=" not in plain
    withb, _ = build_snapshot(src, get_strategy("android"), with_bounds=True)
    assert 'at="60,40"' in withb


def test_ios_bounds_center_from_xywh():
    src = ('<XCUIElementTypeApplication name="A" visible="true">'
           '<XCUIElementTypeButton name="OK" x="10" y="20" width="100" height="40" visible="true"/>'
           "</XCUIElementTypeApplication>")
    withb, _ = build_snapshot(src, get_strategy("ios"), with_bounds=True)
    assert 'at="60,40"' in withb


def test_center_none_when_geometry_absent():
    assert get_strategy("android").center({}) is None
    assert get_strategy("android").center({"bounds": "garbage"}) is None
    assert get_strategy("ios").center({"x": "1"}) is None  # incomplete


# --- more fixtures (§4.2): legacy <node class=...>, duplicate rows -----------

def test_android_legacy_node_class_source():
    # Old-style UiAutomator dumps wrap every element in <node class="...">;
    # effective_tag must fall back to @class through the whole pipeline.
    xml, refmap = build_snapshot((FIX / "android_legacy_nodes.xml").read_text(),
                                 get_strategy("android"))
    # Tags come from @class and are shortened; the literal "node" never leaks.
    assert "<node" not in xml and "android.widget" not in xml
    assert "<Button" in xml and "<TextView" in xml and "<EditText" in xml
    # Pure layout containers (only a resource-id) are still dropped.
    assert 'id="content"' not in xml and 'id="wrap"' not in xml
    # Content is extracted; the EditText binds to its id, not mutable text.
    assert 'text="OK"' in xml and "Legacy" in xml
    edit = next(loc for loc in refmap.values() if loc.value == "com.x:id/field")
    assert edit.by == "id"
    assert _refs_are_sequential(refmap)


def test_android_duplicates_fixture_dedupes_to_unique_xpaths():
    src = (FIX / "android_duplicates.xml").read_text()
    _, refmap = build_snapshot(src, get_strategy("android"))
    rows = [loc for loc in refmap.values() if loc.text == "Duplicate"]
    assert len(rows) == 3
    values = [loc.value for loc in rows]
    assert len(set(values)) == 3, f"rows still collide: {values}"
    assert all(loc.by == "xpath" and _resolves_uniquely(src, loc.value) for loc in rows)
