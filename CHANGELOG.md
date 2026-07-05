# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-05

### Added
- `alert` command for handling system permission dialogs / native alerts.
- `get` command to read a ref's live state without taking a fresh snapshot.
- `url` command for opening deep links.
- Richer `tap`: `--text`, `--at` coordinates, `--long`, and `--double`.
- `snapshot --bounds` to emit element center points.
- Force-string escape hatch for `--cap` values on `open`.
- CI: ruff + unit tests across a Python 3.10–3.13 matrix.

### Changed
- Trimmed snapshot output for token economy.
- Deduplicate colliding locators at snapshot time so refs stay unambiguous.
- Version is now sourced solely from `appium_pilot.__version__` (single source of truth).

## [0.1.0] - 2026-06-28

### Added
- Initial release: agent-first, session-based CLI for driving native mobile
  apps (iOS Simulator / Android Emulator) via Appium. Core loop of
  `open` → `snapshot` → act-by-ref (`tap`/`type`/`scroll`/`swipe`/`wait`),
  plus `devices`, `doctor`, and bundled agent skill install.

[0.2.0]: https://github.com/theperu/appium-pilot/releases/tag/v0.2.0
[0.1.0]: https://github.com/theperu/appium-pilot/releases/tag/v0.1.0
