"""`get` element-state extraction (§2.3), driven by a fake WebElement.

Each strategy reports the attributes that matter on its platform; the command
layer just formats them, so coverage lives on element_state.
"""

from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")


class _El:
    def __init__(self, text="", attrs=None, enabled=True):
        self.text = text
        self._attrs = attrs or {}
        self._enabled = enabled

    def get_attribute(self, name):
        return self._attrs.get(name)

    def is_enabled(self):
        return self._enabled


def test_android_state_text_and_enabled():
    st = AND.element_state(_El(text="hello", enabled=True))
    assert st == {"text": "hello", "enabled": True}


def test_android_state_reports_checked_only_for_checkables():
    plain = AND.element_state(_El(text="x", attrs={"checkable": "false"}))
    assert "checked" not in plain
    toggle = AND.element_state(_El(attrs={"checkable": "true", "checked": "true"}))
    assert toggle["checked"] is True
    off = AND.element_state(_El(attrs={"checkable": "true", "checked": "false"}))
    assert off["checked"] is False


def test_android_state_includes_content_desc():
    st = AND.element_state(_El(attrs={"content-desc": "Add"}))
    assert st["desc"] == "Add"


def test_android_state_ignores_null_string_content_desc():
    # UiAutomator2 returns the literal "null" for an absent content-desc.
    st = AND.element_state(_El(text="x", attrs={"content-desc": "null"}))
    assert "desc" not in st


def test_ios_state_prefers_value_for_typed_content():
    # After typing, the field's contents live in `value`.
    st = IOS.element_state(_El(attrs={"label": "IntegerA", "value": "246", "name": "IntegerA"}))
    assert st["value"] == "246"
    assert st["label"] == "IntegerA"
    assert st["enabled"] is True
    # name duplicates label → dropped.
    assert "name" not in st


def test_ios_state_keeps_name_when_distinct_from_label():
    st = IOS.element_state(_El(attrs={"label": "Clear", "name": "Query"}))
    assert st["name"] == "Query"
