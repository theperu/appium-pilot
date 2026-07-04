"""Locks in the per-platform best_locator rules — every locator bug we fixed."""

from appium.webdriver.common.appiumby import AppiumBy

from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")


# --- Android ---------------------------------------------------------------

def test_android_list_row_disambiguated_by_text():
    # android:id/title repeats per row → must combine resource-id + text.
    loc = AND.best_locator(
        {"resource-id": "android:id/title", "text": "Views", "class": "android.widget.TextView"}, "/x"
    )
    assert loc.by == AppiumBy.XPATH
    assert "resource-id='android:id/title'" in loc.value
    assert "text='Views'" in loc.value


def test_android_edittext_uses_id_only_not_text():
    # An input's text mutates as you type → never bind its locator to text.
    loc = AND.best_locator(
        {"resource-id": "com.x:id/search", "text": "Search", "class": "android.widget.EditText"}, "/x"
    )
    assert loc.by == AppiumBy.ID
    assert loc.value == "com.x:id/search"


def test_android_content_desc_is_accessibility_id():
    loc = AND.best_locator({"content-desc": "Add", "class": "android.widget.ImageButton"}, "/x")
    assert loc.by == AppiumBy.ACCESSIBILITY_ID
    assert loc.value == "Add"


def test_android_text_only_falls_back_to_text_xpath():
    loc = AND.best_locator({"text": "Hello", "class": "android.widget.TextView"}, "/x")
    assert loc.by == AppiumBy.XPATH
    assert "text='Hello'" in loc.value


def test_android_display_text_precedence():
    assert AND.display_text({"text": "T", "content-desc": "D"}) == "T"
    assert AND.display_text({"content-desc": "D"}) == "D"


# --- iOS -------------------------------------------------------------------

def test_ios_name_qualified_by_type():
    loc = IOS.best_locator(
        {"name": "IntegerA", "label": "IntegerA", "type": "XCUIElementTypeTextField"}, "/x"
    )
    assert loc.by == AppiumBy.IOS_PREDICATE
    assert "type == 'XCUIElementTypeTextField'" in loc.value
    assert "name == 'IntegerA'" in loc.value


def test_ios_same_name_different_type_yields_distinct_locators():
    a = IOS.best_locator({"name": "Query", "type": "XCUIElementTypeSearchField"}, "/x")
    b = IOS.best_locator({"name": "Query", "type": "XCUIElementTypeButton"}, "/x")
    assert a.value != b.value


def test_ios_label_fallback_predicate():
    loc = IOS.best_locator({"label": "Submit", "type": "XCUIElementTypeButton"}, "/x")
    assert loc.by == AppiumBy.IOS_PREDICATE
    assert "label == 'Submit'" in loc.value


def test_ios_display_text_precedence():
    assert IOS.display_text({"label": "L", "value": "V", "name": "N"}) == "L"
    assert IOS.display_text({"label": "", "value": "V", "name": "N"}) == "V"
    assert IOS.display_text({"name": "N"}) == "N"


# --- literal quoting + unicode in locators (§4.2) ---------------------------

from appium_pilot.strategies.android import _q  # noqa: E402
from appium_pilot.strategies.ios import _pq  # noqa: E402


def test_android_xpath_quoting():
    assert _q("hello") == "'hello'"                 # no quotes → single-quote wrap
    assert _q("it's") == '"it\'s"'                  # has ' → double-quote wrap
    assert _q('say "hi"') == "'say \"hi\"'"        # has " → single-quote wrap
    both = _q("mix'and\"quote")                     # has both → concat()
    assert both.startswith("concat(") and "\"'\"" in both
    assert _q("Add 🎉") == "'Add 🎉'"               # emoji pass through verbatim


def test_ios_predicate_quoting():
    assert _pq("hello") == "'hello'"
    assert _pq("it's") == "'it\\'s'"                # single quote escaped
    assert _pq("a\\b") == "'a\\\\b'"                # backslash escaped first
    assert _pq("Cool 🎉") == "'Cool 🎉'"            # emoji pass through verbatim


def test_quoted_text_builds_wellformed_locator():
    # An apostrophe in text must not break the generated xpath predicate.
    src = ('<hierarchy><android.widget.TextView resource-id="com.x:id/t" '
           "text=\"it's here\"/></hierarchy>")
    from appium_pilot.snapshot import build_snapshot
    _, refmap = build_snapshot(src, get_strategy("android"))
    (loc,) = refmap.values()
    assert "it's here" in loc.value and loc.value.startswith("//*[@resource-id=")
