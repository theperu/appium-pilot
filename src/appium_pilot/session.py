"""Session state: persist to disk, create new sessions, reconnect to live ones.

The Appium server keeps the WebDriver session alive between invocations; we only
persist the handle ({serverUrl, sessionId, platform, caps, device, refmap}) and
reattach to the existing server-side session each call.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from appium import webdriver
from appium.options.common import AppiumOptions

from appium_pilot import config
from appium_pilot.output import CommandError
from appium_pilot.strategies import Locator, PlatformStrategy, get_strategy


@dataclass
class Session:
    name: str
    server_url: str
    session_id: str
    platform: str
    device: str
    caps: dict = field(default_factory=dict)
    # ref -> locator dict; the most recent snapshot's mapping.
    refmap: dict = field(default_factory=dict)
    recording: bool = False
    # Ordered log of ref-free steps this session ran (for `flow save`/`replay`).
    log: list = field(default_factory=list)

    # -- persistence --------------------------------------------------------

    def save(self) -> None:
        config.ensure_dirs()
        config.session_file(self.name).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, name: str) -> "Session":
        path = config.session_file(name)
        if not path.exists():
            raise CommandError(
                f"no session '{name}'. Run `appium-pilot{_dash(name)} open ...` first."
            )
        return cls(**json.loads(path.read_text()))

    def delete(self) -> None:
        config.session_file(self.name).unlink(missing_ok=True)

    # -- refmap -------------------------------------------------------------

    def set_refmap(self, refmap: dict[str, Locator]) -> None:
        self.refmap = {ref: loc.to_dict() for ref, loc in refmap.items()}

    def locator_for(self, ref: str) -> Locator:
        entry = self.refmap.get(ref)
        if entry is None:
            raise CommandError(
                f"unknown ref '{ref}'. Refs come from the latest `snapshot`; run snapshot again.",
                code=2,
            )
        return Locator.from_dict(entry)

    # -- command log (flow record/replay) -----------------------------------

    def append_step(self, step: dict) -> None:
        """Record one ref-free step; persisted with the session handle."""
        self.log.append(step)

    def clear_log(self) -> None:
        self.log = []

    # -- helpers ------------------------------------------------------------

    @property
    def strategy(self) -> PlatformStrategy:
        return get_strategy(self.platform)

    @property
    def app_id(self) -> Optional[str]:
        """The bundleId/appPackage of the app under test, if known."""
        return self.caps.get("appium:appPackage") or self.caps.get("appium:bundleId")

    def attach(self):
        """Reconnect to the live server-side session (no new session created)."""
        driver = attach_driver(self.server_url, self.session_id, self.caps)
        driver.implicitly_wait(config.IMPLICIT_WAIT)
        return driver


def _dash(name: str) -> str:
    return "" if name == "default" else f" -s={name}"


def new_driver(server_url: str, caps: dict):
    """Create a brand-new Appium session."""
    options = AppiumOptions()
    options.load_capabilities(caps)
    return webdriver.Remote(command_executor=server_url, options=options)


def attach_driver(server_url: str, session_id: str, caps: Optional[dict] = None):
    """Attach to an already-running session by intercepting session creation.

    Selenium's Remote always calls start_session() during construction; we
    override it to bind the existing sessionId instead of opening a new one.
    """

    class _Attached(webdriver.Remote):
        def start_session(self, capabilities):  # noqa: ANN001, D401
            self.session_id = session_id
            self.caps = caps or {}

    options = AppiumOptions()
    options.load_capabilities(caps or {})
    return _Attached(command_executor=server_url, options=options)
