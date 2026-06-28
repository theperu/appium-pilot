"""PlatformStrategy — the abstraction over iOS/Android divergence.

Modeled on the sossoldi `MobileActions` pattern: shared verbs live here; only
the truly platform-specific bits (display-text extraction, best-locator
selection, what counts as a meaningful node, gestures, key presses) are
overridden in the AndroidStrategy / IOSStrategy subclasses.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

DIRECTIONS = ("up", "down", "left", "right")


@dataclass
class Locator:
    by: str  # an AppiumBy value, e.g. "accessibility id", "id", "xpath"
    value: str
    text: str = ""  # display text captured at snapshot time (for error messages)

    def to_dict(self) -> dict:
        return {"by": self.by, "value": self.value, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict) -> "Locator":
        return cls(by=d["by"], value=d["value"], text=d.get("text", ""))


class PlatformStrategy(ABC):
    platform: str

    # ---- snapshot extraction (overridden per platform) --------------------

    @staticmethod
    def effective_tag(el: ET.Element) -> str:
        """The class name to use as the node's identity.

        Android page source historically wraps everything in <node class="...">;
        newer drivers (and iOS) use the class name as the tag directly.
        """
        return el.attrib.get("class") or el.tag

    @abstractmethod
    def is_meaningful(self, el: ET.Element) -> bool:
        """Whether this node survives the filtered snapshot (gets a ref)."""

    @abstractmethod
    def display_text(self, attrs: dict) -> str:
        """Human-visible label for the node, per platform attribute precedence."""

    @abstractmethod
    def best_locator(self, attrs: dict, xpath: str) -> Locator:
        """Most robust locator for the node, per platform preference order."""

    @abstractmethod
    def kept_attrs(self, attrs: dict) -> dict:
        """Attributes worth keeping in the filtered XML (token economy)."""

    # ---- gestures (divergent; native primary, coordinate fallback) --------

    def swipe(self, driver, direction: str, amount: float = 1.0) -> None:  # noqa: ANN001
        try:
            self._native_swipe(driver, direction, amount)
        except Exception:  # noqa: BLE001 — native gesture unsupported; fall back to coords
            self._coord_swipe(driver, direction, amount)

    @abstractmethod
    def _native_swipe(self, driver, direction: str, amount: float) -> None:  # noqa: ANN001
        ...

    def _coord_swipe(self, driver, direction: str, amount: float) -> None:  # noqa: ANN001
        size = driver.get_window_size()
        w, h = size["width"], size["height"]
        cx, cy = w // 2, h // 2
        dx, dy = int(w * 0.4 * amount), int(h * 0.4 * amount)
        moves = {
            "up": (cx, cy + dy, cx, cy - dy),
            "down": (cx, cy - dy, cx, cy + dy),
            "left": (cx + dx, cy, cx - dx, cy),
            "right": (cx - dx, cy, cx + dx, cy),
        }
        x1, y1, x2, y2 = moves[direction]
        driver.swipe(x1, y1, x2, y2, 400)

    @abstractmethod
    def scroll_to_element(self, driver, element) -> None:  # noqa: ANN001
        """Scroll until `element` is on screen."""

    @abstractmethod
    def scroll_to_text(self, driver, text: str):  # noqa: ANN001
        """Scroll until an element containing `text` is found; return it or None."""

    @abstractmethod
    def press_key(self, driver, key: str) -> None:  # noqa: ANN001
        """Press a hardware/system key (back/home/enter/...)."""

    @abstractmethod
    def find_by_text(self, driver, text: str):  # noqa: ANN001
        """Find an element whose visible text contains `text`; return it or None."""

    def submit(self, driver, element) -> None:  # noqa: ANN001
        """Confirm text entry (the keyboard's return/enter)."""
        element.send_keys("\n")

    def hide_keyboard(self, driver) -> None:  # noqa: ANN001
        driver.hide_keyboard()

    def recording_options(self, time_limit: int, quality: str) -> dict:
        """Options for start_recording_screen. timeLimit is common to both drivers."""
        return {"timeLimit": str(time_limit)}


def _truthy(value: Optional[str]) -> bool:
    return str(value).lower() == "true"
