# appium-pilot

An agent-first, session-based CLI for driving native mobile apps via Appium.
One verb per invocation, state persisted across calls, output tuned for an LLM
agent: `snapshot` the screen to get element refs, then act on them by ref.

## Install

```bash
pipx install .          # or: pip install -e .
```

You also need Node + the Appium server and drivers (appium-pilot does not install
them — run `appium-pilot doctor` to see what's missing):

```bash
npm i -g appium
appium driver install uiautomator2   # Android
appium driver install xcuitest       # iOS
```

## Quick start

```bash
# Launch an installed Android app (auto-picks a booted emulator)
appium-pilot open --platform android --app-package com.example.app

# Or an iOS Simulator app bundle
appium-pilot open --platform ios --app /path/to/MyApp.app

# Inspect the screen — returns filtered XML with e1..eN refs
appium-pilot snapshot

# Act on a ref from the latest snapshot
appium-pilot tap e7

# Record a flow once, then replay it forever (deterministic regression)
appium-pilot flow save checkout.yaml
appium-pilot flow replay checkout.yaml

# Multiple parallel sessions
appium-pilot -s=checkout open --platform ios --app /path/to/MyApp.app
```

Session state lives under `~/.appium-pilot/` (so any invocation can reattach
regardless of cwd). Artifacts you want to find — screenshots and videos — are
written to `./appium-pilot/` in the current directory (override with
`APPIUM_PILOT_OUTPUT`).

## Use from AI coding agents

A skill ships inside the package so agents discover the commands and drive the
CLI themselves. Install it into whichever tool you use — no manual symlink:

```bash
appium-pilot skills install                # Claude Code (~/.claude/skills/), the default
appium-pilot skills install --tool cursor  # Cursor       (.cursor/rules/)
appium-pilot skills install --tool copilot # GitHub Copilot (.github/copilot-instructions.md)
appium-pilot skills install --tool agents  # AGENTS.md (the cross-tool standard)
appium-pilot skills install --tool all     # all of the above
appium-pilot skills uninstall --tool all   # remove
```

`claude` installs user-level (once, for every project); the others write into the
current project. The skill source lives at `src/appium_pilot/skilldata/SKILL.md`;
re-run `skills install` after editing it.

## Platform support

- **macOS** — full: iOS Simulator + Android Emulator.
- **Windows / Linux** — Android only (iOS needs a Mac). External tools are
  resolved through `shutil.which` (honoring `PATHEXT`, so `appium.cmd`/`adb.exe`
  work) and background processes detach via OS-appropriate flags. On Windows,
  `make` is uncommon — run the underlying commands directly
  (`.venv\Scripts\pytest`, `python -m appium_pilot ...`). The Windows path is
  implemented but not yet exercised on a Windows host.

## Testing

Two tiers (see `tests/`):

```bash
make install          # pip install -e ".[dev]"
make test             # fast unit tests, no device — run after every change
make test-e2e-android # device-backed E2E (auto-boots an emulator)
make test-e2e-ios     # device-backed E2E (auto-boots a simulator)
make test-e2e         # both platforms
```

- **Unit** (`tests/unit/`, ~0.2s, no device): locks in the snapshot filtering,
  per-platform locators, quoting, output/JSON contract, parsing and config logic.
  `pytest` runs only these by default.
- **E2E** (`tests/e2e/`, marked `e2e`): drives the real CLI against official
  Appium sample apps — ApiDemos (Android) and TestApp (iOS, built on demand) —
  covering every command on both platforms. Apps are cached under `tests/_apps/`;
  tests skip cleanly if a device/toolchain is unavailable.

## Status

All v1 commands implemented and smoke-tested end-to-end on an iOS Simulator
(open → snapshot → tap → re-snapshot → screenshot → stale-ref handling → close):

`open` · `close` · `list` · `close-all` · `kill-all` · `snapshot [--raw]` ·
`source` · `screenshot [ref]` · `devices` · `doctor` · `tap` · `type` · `clear` ·
`swipe` · `scroll` · `press` · `hide-keyboard` · `orientation` · `wait` · `get` ·
`expect` · `flow save`/`replay`/`show`/`clear` · `url` · `alert` ·
`video-start`/`video-stop` ·
`launch`/`activate`/`terminate`/`background`/`install`/`remove`/`reset`.

Targets iOS Simulator + Android Emulator. Deferred to v2: hybrid webview,
geolocation, network conditions, deep links, real devices, cloud farms.
