# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-12

### Added
- `expect` command — assert a ref's live state as a test oracle that polls until
  true. Matchers cover display text (`--text`, `--contains`, `--matches`), input
  contents (`--value`), presence (`--visible`, `--gone`), and interactive state
  (`--enabled`/`--disabled`, `--checked`/`--unchecked`). `--all FILE` runs a batch
  of `<ref> <matcher>` checks as soft assertions under one shared `--timeout`.
  Exit codes are a test contract: `0` held, `1` assertion failed
  (expected/actual in `--json`), `2` couldn't be evaluated.
- `expect --baseline IMG` — visual baseline diffing. Screenshots the ref (or the
  full screen) and compares it against a golden image, polling until it matches;
  `--update` captures/overwrites the baseline, `--threshold` and `--pixel-threshold`
  tune sensitivity, and a failing compare writes a diff PNG. Requires the optional
  `visual` extra (Pillow); the command prints an install hint if it's absent.
- `flow` command — record once, replay forever. Every mutating command a session
  runs is logged; `flow save FILE.yaml` dumps it to a portable, ref-free flow
  (each step stores the element's captured locator, not the throwaway `eN`).
  `flow replay FILE.yaml` re-runs it against a live session, self-healing to the
  captured display text when a locator drifts. Recorded `expect` steps are
  re-checked, so a saved flow doubles as a deterministic regression test; exit
  codes mirror `expect` (0 pass / 1 assertion failed / 2 step unrunnable).
  `flow show` and `flow clear` inspect and reset the recorded log.
- `find QUERY` command — token-cheap element lookup by visible text. Prints only
  the matching refs (numbered identically to a full `snapshot`, so refs never
  disagree) while persisting the complete screen refmap, so results are
  immediately actionable by `tap`/`type`. Read-only and view-only: it never
  scrolls (`--case-sensitive` to match case exactly).
- `PyYAML` is now a runtime dependency (flow files are YAML).
- Optional `visual` extra (`pip install 'appium-pilot[visual]'`) pulling in Pillow
  for `expect --baseline`.

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

[0.3.0]: https://github.com/theperu/appium-pilot/releases/tag/v0.3.0
[0.2.0]: https://github.com/theperu/appium-pilot/releases/tag/v0.2.0
[0.1.0]: https://github.com/theperu/appium-pilot/releases/tag/v0.1.0
