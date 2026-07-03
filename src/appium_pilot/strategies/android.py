"""Android (UiAutomator2) strategy."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy

from appium_pilot.output import CommandError
from appium_pilot.strategies.base import Locator, PlatformStrategy, _truthy

# Common Android keycodes for `press`.
KEYCODES = {"back": 4, "home": 3, "enter": 66, "tab": 61, "delete": 67, "search": 84, "menu": 82}


def _q(value: str) -> str:
    """Quote a string as an XPath literal, handling embedded quotes via concat()."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"

# Classes that are interactive even without text/id — keep them in the snapshot.
INTERACTIVE_CLASSES = {
    "android.widget.Button",
    "android.widget.ImageButton",
    "android.widget.EditText",
    "android.widget.CheckBox",
    "android.widget.Switch",
    "android.widget.RadioButton",
    "android.widget.Spinner",
    "android.widget.SeekBar",
}

# Pure layout containers: drop them when they only carry a resource-id (they're
# non-semantic). Their meaningful descendants bubble up to the nearest kept node.
LAYOUT_CLASSES = {
    "android.widget.FrameLayout",
    "android.widget.LinearLayout",
    "android.widget.RelativeLayout",
    "android.widget.TableLayout",
    "android.view.ViewGroup",
    "androidx.cardview.widget.CardView",
    "androidx.constraintlayout.widget.ConstraintLayout",
    "androidx.coordinatorlayout.widget.CoordinatorLayout",
}


# Short (displayed) names of INTERACTIVE_CLASSES — used by try_fold, which sees
# post-short_tag PNodes.
_INTERACTIVE_SHORT = {c.rsplit(".", 1)[-1] for c in INTERACTIVE_CLASSES}


class AndroidStrategy(PlatformStrategy):
    platform = "android"

    def short_tag(self, tag: str) -> str:
        # Drop the package path: android.widget.TextView -> TextView. The full
        # class stays in the locator; the agent acts by ref, not class name.
        return tag.rsplit(".", 1)[-1]

    def is_meaningful(self, el: ET.Element) -> bool:
        a = el.attrib
        if _truthy(a.get("clickable")) or _truthy(a.get("checkable")) or _truthy(a.get("scrollable")):
            return True
        if a.get("text") or a.get("content-desc"):
            return True
        if self.effective_tag(el) in INTERACTIVE_CLASSES:
            return True
        # A resource-id makes a node addressable, but skip pure layout containers.
        return bool(a.get("resource-id")) and self.effective_tag(el) not in LAYOUT_CLASSES

    def display_text(self, attrs: dict) -> str:
        return attrs.get("text") or attrs.get("content-desc") or ""

    def best_locator(self, attrs: dict, xpath: str) -> Locator:
        text = attrs.get("text")
        desc = attrs.get("content-desc")
        rid = attrs.get("resource-id")
        display = self.display_text(attrs)
        # An input field's text mutates as you type, so never bind its locator to
        # text — prefer the (stable) resource-id alone.
        cls = attrs.get("class") or attrs.get("type") or ""
        is_input = "EditText" in cls or "AutoComplete" in cls

        # content-desc is usually unique and stable.
        if desc:
            return Locator(AppiumBy.ACCESSIBILITY_ID, desc, display)
        # resource-id alone is often NOT unique (e.g. android:id/title repeats per
        # list row), so combine it with text when we have both — except for inputs.
        if rid and text and not is_input:
            return Locator(AppiumBy.XPATH, f'//*[@resource-id={_q(rid)} and @text={_q(text)}]', display)
        if rid:
            return Locator(AppiumBy.ID, rid, display)
        if text and not is_input:
            return Locator(AppiumBy.XPATH, f"//*[@text={_q(text)}]", display)
        return Locator(AppiumBy.XPATH, xpath, display)

    def kept_attrs(self, attrs: dict) -> dict:
        out: dict = {}
        if attrs.get("text"):
            out["text"] = attrs["text"]
        if attrs.get("content-desc"):
            out["desc"] = attrs["content-desc"]
        if attrs.get("resource-id"):
            # Display-only: `com.x:id/row` -> `row`. The locator (best_locator)
            # keeps the full resource-id; the shown id is informational and the
            # package prefix repeats on every node for no signal.
            out["id"] = attrs["resource-id"].split(":id/", 1)[-1]
        if _truthy(attrs.get("clickable")):
            out["clickable"] = "true"
        if attrs.get("enabled") == "false":
            out["enabled"] = "false"
        return out

    def try_fold(self, parent, child):  # noqa: ANN001
        # Only fold a lone text/desc leaf into a clickable container; never fold
        # anything interactive in its own right (inputs, buttons, ...).
        if parent.attrs.get("clickable") != "true":
            return None
        if child.attrs.get("clickable") or child.tag in _INTERACTIVE_SHORT:
            return None
        text, desc = child.attrs.get("text"), child.attrs.get("desc")
        if not (text or desc):
            return None
        if text and parent.attrs.get("text") not in (None, text):
            return None  # parent has its own, different text — keep both nodes
        if text:
            parent.attrs["text"] = text
        if desc and not parent.attrs.get("desc"):
            parent.attrs["desc"] = desc
        # A parent content-desc backs an accessibility-id locator (strongest);
        # otherwise the child's text-based locator is the reliably findable one.
        return "parent" if parent.attrs.get("desc") else "child"

    # ---- gestures ---------------------------------------------------------

    def _native_swipe(self, driver, direction: str, amount: float) -> None:  # noqa: ANN001
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: scrollGesture",
            {
                "left": int(size["width"] * 0.1),
                "top": int(size["height"] * 0.1),
                "width": int(size["width"] * 0.8),
                "height": int(size["height"] * 0.8),
                "direction": direction,
                "percent": amount,
                "speed": 2000,
            },
        )

    def scroll_to_element(self, driver, element) -> None:  # noqa: ANN001
        # Scroll the element's container; best-effort (UiAutomator2 has no toVisible).
        driver.execute_script(
            "mobile: scrollGesture",
            {"elementId": element.id, "direction": "down", "percent": 0.8, "speed": 2000},
        )

    def scroll_to_text(self, driver, text: str):  # noqa: ANN001
        selector = (
            "new UiScrollable(new UiSelector().scrollable(true))"
            f'.scrollIntoView(new UiSelector().textContains("{text}"))'
        )
        try:
            return driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector)
        except Exception:  # noqa: BLE001
            return None

    def press_key(self, driver, key: str) -> None:  # noqa: ANN001
        code = KEYCODES.get(key.lower())
        if code is None and key.isdigit():
            code = int(key)
        if code is None:
            raise CommandError(
                f"unknown key {key!r} for android (try {', '.join(KEYCODES)} or a numeric keycode)"
            )
        driver.press_keycode(code)

    def submit(self, driver, element) -> None:  # noqa: ANN001
        driver.press_keycode(KEYCODES["enter"])

    def find_by_text(self, driver, text: str):  # noqa: ANN001
        selector = f'new UiSelector().textContains("{text}")'
        try:
            return driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector)
        except Exception:  # noqa: BLE001
            return None
