"""Shared ref → live-element resolution used by tap/type/clear/scroll/etc.

Re-finds the element by the locator stored at snapshot time. Refs are valid only
until the next snapshot; if the locator no longer matches uniquely we fail with a
clear, actionable error (no silent re-snapshot).
"""

from __future__ import annotations

import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)

from appium_pilot.output import CommandError
from appium_pilot.strategies import Locator


def find_ref(driver, locator: Locator, ref: str):  # noqa: ANN001
    """Return the single live element for `ref`, or raise CommandError(code=2)."""
    last_err: Exception | None = None
    for _ in range(2):  # one stale-element retry, mirroring the sossoldi base
        try:
            matches = driver.find_elements(by=locator.by, value=locator.value)
            if not matches:
                raise CommandError(
                    f"ref {ref} ({locator.by}={locator.value!r}) no longer matches; "
                    "the screen changed — run `snapshot` again.",
                    code=2,
                )
            if len(matches) > 1:
                raise CommandError(
                    f"ref {ref} is now ambiguous ({len(matches)} matches); run `snapshot` again.",
                    code=2,
                )
            return matches[0]
        except StaleElementReferenceException as exc:
            last_err = exc
            time.sleep(0.5)
        except NoSuchElementException as exc:
            raise CommandError(f"ref {ref} not found; run `snapshot` again.", code=2) from exc
    raise CommandError(f"could not resolve {ref}: {last_err}")
