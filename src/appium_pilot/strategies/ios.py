"""iOS (XCUITest) strategy."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy

from appium_pilot.output import CommandError
from appium_pilot.strategies.base import Locator, PlatformStrategy


def _pq(value: str) -> str:
    """Quote a string for an NSPredicate literal (escape backslashes and quotes)."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

# XCUIElementType* tags that are interactive even without a label.
INTERACTIVE_TYPES = {
    "XCUIElementTypeButton",
    "XCUIElementTypeTextField",
    "XCUIElementTypeSecureTextField",
    "XCUIElementTypeTextView",
    "XCUIElementTypeSwitch",
    "XCUIElementTypeSlider",
    "XCUIElementTypeCell",
    "XCUIElementTypeLink",
    "XCUIElementTypeSearchField",
    "XCUIElementTypeSegmentedControl",
}


# Post-short_tag names, for try_fold (which sees shortened PNodes).
_INTERACTIVE_SHORT = {t.removeprefix("XCUIElementType") for t in INTERACTIVE_TYPES}
_FOLD_PARENTS = {"Cell", "Button", "Link"}


class IOSStrategy(PlatformStrategy):
    platform = "ios"

    def short_tag(self, tag: str) -> str:
        # Strip the ubiquitous XCUIElementType prefix: it's on every node and
        # tokenizes poorly. XCUIElementTypeButton -> Button.
        prefix = "XCUIElementType"
        return tag[len(prefix):] if tag.startswith(prefix) else tag

    def is_meaningful(self, el: ET.Element) -> bool:
        a = el.attrib
        # Invisible nodes are noise on iOS; drop them outright.
        if a.get("visible") == "false":
            return False
        if a.get("name") or a.get("label") or a.get("value"):
            return True
        return self.effective_tag(el) in INTERACTIVE_TYPES

    def display_text(self, attrs: dict) -> str:
        # iOS precedence: label > value > name (mirrors the sossoldi fallback).
        return attrs.get("label") or attrs.get("value") or attrs.get("name") or ""

    def best_locator(self, attrs: dict, xpath: str) -> Locator:
        text = self.display_text(attrs)
        name = attrs.get("name")
        label = attrs.get("label")
        typ = attrs.get("type")
        # A bare accessibility id (name) is often NOT unique (e.g. several
        # "Search"/"Dictate" elements), so qualify it by element type when we can.
        if name and typ:
            return Locator(AppiumBy.IOS_PREDICATE, f"type == '{typ}' AND name == {_pq(name)}", text)
        if name:
            return Locator(AppiumBy.ACCESSIBILITY_ID, name, text)
        if label and typ:
            return Locator(AppiumBy.IOS_PREDICATE, f"type == '{typ}' AND label == {_pq(label)}", text)
        if label:
            return Locator(AppiumBy.IOS_PREDICATE, f"label == {_pq(label)}", text)
        return Locator(AppiumBy.XPATH, xpath, text)

    def kept_attrs(self, attrs: dict) -> dict:
        out: dict = {}
        name = attrs.get("name")
        label = attrs.get("label")
        if name:
            out["name"] = name
        # iOS very often sets label == name; the duplicate is pure token waste.
        if label and label != name:
            out["label"] = label
        if attrs.get("value"):
            out["value"] = attrs["value"]
        if attrs.get("enabled") == "false":
            out["enabled"] = "false"
        return out

    def element_state(self, element) -> dict:  # noqa: ANN001
        # iOS carries current input contents in `value` (what you type lands
        # there), plus the static label; name is dropped when it duplicates label.
        out: dict = {}
        label = element.get_attribute("label")
        value = element.get_attribute("value")
        name = element.get_attribute("name")
        if label:
            out["label"] = label
        if value:
            out["value"] = value
        if name and name != label:
            out["name"] = name
        out["enabled"] = element.is_enabled()
        return out

    def try_fold(self, parent, child):  # noqa: ANN001
        # Cells/Buttons/Links wrapping a single StaticText-style label are one
        # tappable thing (a Button's label is routinely duplicated as a child).
        if parent.tag not in _FOLD_PARENTS:
            return None
        if child.tag in _INTERACTIVE_SHORT:
            return None
        text = child.attrs.get("label") or child.attrs.get("name")
        if not text:
            return None
        own = parent.attrs.get("label") or parent.attrs.get("name")
        if own not in (None, text):
            return None  # parent has its own, different label — keep both nodes
        if not own:
            parent.attrs["label"] = text
        if child.attrs.get("value") and not parent.attrs.get("value"):
            parent.attrs["value"] = child.attrs["value"]
        # A parent name backs a type+name predicate (strong); otherwise the
        # child's label-based locator is the reliably findable one.
        return "parent" if parent.attrs.get("name") else "child"

    # ---- gestures ---------------------------------------------------------

    def gesture_tap(self, driver, kind, element=None, x=None, y=None, duration=1.0) -> None:  # noqa: ANN001
        target = {"elementId": element.id} if element is not None else {"x": x, "y": y}
        if kind == "long":
            # XCUITest durations are seconds (Android's are ms).
            driver.execute_script("mobile: touchAndHold", {**target, "duration": duration})
        elif kind == "double":
            driver.execute_script("mobile: doubleTap", target)
        else:  # single tap at a coordinate
            driver.execute_script("mobile: tap", target)

    def _native_swipe(self, driver, direction: str, amount: float) -> None:  # noqa: ANN001
        driver.execute_script("mobile: swipe", {"direction": direction})

    def scroll_to_element(self, driver, element) -> None:  # noqa: ANN001
        driver.execute_script("mobile: scroll", {"elementId": element.id, "toVisible": True})

    def scroll_to_text(self, driver, text: str):  # noqa: ANN001
        # XCUITest has no scroll-to-text and no canScrollMore signal, so we cap
        # iterations and try both directions (the target may be above us).
        q = _pq(text)
        predicate = f"label CONTAINS {q} OR name CONTAINS {q} OR value CONTAINS {q}"
        for direction in ("up", "down"):
            for _ in range(12):
                matches = driver.find_elements(AppiumBy.IOS_PREDICATE, predicate)
                if matches:
                    return matches[0]
                driver.execute_script("mobile: swipe", {"direction": direction})
        return None

    def press_key(self, driver, key: str) -> None:  # noqa: ANN001
        k = key.lower()
        if k == "home":
            driver.execute_script("mobile: pressButton", {"name": "home"})
        elif k == "enter":
            driver.execute_script("mobile: keys", {"keys": ["\n"]})
        else:
            raise CommandError(
                f"key {key!r} not supported on iOS (only 'home' and 'enter'; there is no system back)"
            )

    def find_by_text(self, driver, text: str):  # noqa: ANN001
        q = _pq(text)
        predicate = f"label CONTAINS {q} OR name CONTAINS {q} OR value CONTAINS {q}"
        try:
            return driver.find_element(AppiumBy.IOS_PREDICATE, predicate)
        except Exception:  # noqa: BLE001
            return None

    def recording_options(self, time_limit: int, quality: str) -> dict:
        # videoQuality is iOS-only (low/medium/high); Android ignores it.
        return {"timeLimit": str(time_limit), "videoQuality": quality}

    def hide_keyboard(self, driver) -> None:  # noqa: ANN001
        # iOS keyboards often need an explicit Done/Return tap rather than hideKeyboard.
        for label in ("Done", "Return", "return", "Go", "Search"):
            try:
                driver.find_element(AppiumBy.ACCESSIBILITY_ID, label).click()
                return
            except Exception:  # noqa: BLE001
                continue
        try:
            driver.hide_keyboard()
        except Exception:  # noqa: BLE001
            pass
