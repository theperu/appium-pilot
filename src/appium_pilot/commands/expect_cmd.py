"""`expect` — assert a ref's live state; a test oracle that polls until true.

Unlike `tap`/`get`, expect must treat "the ref no longer resolves" as an
assertion *outcome*, not a hard error: for `--gone` zero matches is success, for
every other matcher it's a failure. So it resolves leniently (never through
`find_ref`, which raises) and, when the poll window elapses, reports the last
state it observed so the failure carries a real expected-vs-actual diff.

`--all FILE` runs a batch of checks — one `<ref> <matcher>` line in the *same*
grammar as a single call (soft assertions: judge them all, don't stop at the
first miss). The whole set shares one `--timeout`; each poll re-checks only the
not-yet-passed lines, and a pass sticks.

Exit codes mirror a test oracle:
  0  assertion(s) held
  1  an assertion failed — the app is in the wrong state (expected/actual in --json)
  2  could not be evaluated — no session, ambiguous ref, non-checkable element
     (in a batch, 1 outranks 2: a real failure sets the exit code, errors only surface
     it when nothing outright failed)
"""

from __future__ import annotations

import argparse
import re
import shlex
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from appium_pilot import config
from appium_pilot.output import CommandError, emit
from appium_pilot.session import Session

# Fields from element_state() a text assertion may match against. The precise
# matchers target one aspect (a label vs. typed contents); the fuzzy ones search
# everything visible, since "does this text appear here" shouldn't care whether
# it sits in a label or a value (Android puts contents in `text`, iOS in `value`).
_LABEL_FIELDS = ("text", "desc", "label", "name")          # --text: what the user reads
_VALUE_FIELDS = ("value", "text")                          # --value: what the user typed
_ANY_FIELDS = ("text", "desc", "label", "name", "value")   # --contains/--matches: anywhere

_POLL = 0.3  # seconds between polls, matching wait_cmd

# Matchers that take a string argument, in precedence order.
_STRING_MATCHERS = ("text", "contains", "matches", "value")
# Boolean state matchers (store_true flags).
_FLAG_MATCHERS = ("visible", "gone", "enabled", "disabled", "checked", "unchecked")


def _add_matcher_group(parser: argparse.ArgumentParser, required: bool):
    """The matcher flags, defined once so `expect` and a batch line share a grammar."""
    g = parser.add_mutually_exclusive_group(required=required)
    g.add_argument("--text", metavar="S", help="display text equals S exactly")
    g.add_argument("--contains", metavar="S", help="display text contains substring S")
    g.add_argument("--matches", metavar="RE", help="display text matches regex RE")
    g.add_argument("--value", metavar="S", help="input contents equal S exactly")
    g.add_argument("--visible", action="store_true", help="present and displayed")
    g.add_argument("--gone", action="store_true", help="absent or not displayed")
    g.add_argument("--enabled", action="store_true", help="present and enabled")
    g.add_argument("--disabled", action="store_true", help="present and disabled")
    g.add_argument("--checked", action="store_true", help="checkable and checked/on")
    g.add_argument("--unchecked", action="store_true", help="checkable and unchecked/off")
    return g


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("expect", help="assert a ref's state, or a batch of checks (exit 0 pass / 1 fail)")
    p.add_argument("ref", nargs="?", help="element ref from the latest snapshot")
    g = _add_matcher_group(p, required=False)  # required-ness is validated in run() (ref vs --all)
    # --baseline joins the matcher group here (not in _add_matcher_group), so it is
    # available to a single `expect` but NOT to batch lines, which reuse the helper.
    g.add_argument("--baseline", metavar="IMG",
                   help="screenshot the ref (or full screen) and compare against baseline IMG")
    p.add_argument("--all", metavar="FILE", dest="all_file",
                   help="run a file of checks — one `<ref> <matcher>` per line ('-' for stdin)")
    p.add_argument("--timeout", type=float, default=5.0,
                   help="seconds to poll until the assertion(s) hold (default 5)")
    # Visual-diff modifiers — only meaningful with --baseline.
    p.add_argument("--update", action="store_true",
                   help="with --baseline: capture and (over)write the baseline instead of comparing")
    p.add_argument("--threshold", type=float, default=0.001,
                   help="with --baseline: max fraction of pixels allowed to differ (default 0.001)")
    p.add_argument("--pixel-threshold", dest="pixel_threshold", type=int, default=16,
                   help="with --baseline: per-channel color delta ignored as noise, 0-255 (default 16)")
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    if args.all_file:
        if args.ref or _selected_matcher(args):
            raise CommandError("--all cannot be combined with a ref or a matcher")
        _run_batch(session, args)
        return
    matcher = _selected_matcher(args)
    if matcher and matcher[0] == "baseline":
        _run_visual(session, args, args.ref, matcher[1])  # ref optional: element vs full screen
        return
    if args.update:
        raise CommandError("--update only applies with --baseline")
    if not args.ref:
        raise CommandError("expect needs a ref (or --all FILE)")
    if matcher is None:
        raise CommandError("expect needs a matcher (e.g. --visible, --text S, --gone, --baseline)")
    _run_single(session, args, args.ref, *matcher)


# --- single assertion ------------------------------------------------------

def _run_single(session: Session, args, ref: str, kind: str, expected: str | None) -> None:
    locator = session.locator_for(ref)
    driver = session.attach()
    driver.implicitly_wait(0)  # explicit polling owns timing (mirrors wait_cmd)
    strategy = session.strategy

    deadline = time.monotonic() + args.timeout
    result = Match(False, "not evaluated")
    while True:
        matches = driver.find_elements(by=locator.by, value=locator.value)
        result = evaluate(strategy, kind, expected, matches)
        if result.ok:
            emit(_ok_message(ref, kind, expected), ref=ref, check=kind)
            return
        if time.monotonic() >= deadline:
            break
        time.sleep(_POLL)

    if not result.evaluable:
        raise CommandError(f"{ref}: {result.actual}", code=2, ref=ref, check=kind)
    raise CommandError(
        _fail_message(ref, kind, expected, result.actual, args.timeout),
        code=1, ref=ref, check=kind, expected=expected, actual=result.actual,
    )


# --- visual baseline (--baseline) ------------------------------------------

def _run_visual(session: Session, args, ref: str | None, baseline_path: str) -> None:
    driver = session.attach()
    element = None
    if ref:
        driver.implicitly_wait(0)
        element = _resolve_single(driver, session.locator_for(ref), ref)

    if args.update:
        path = Path(baseline_path)
        existed = path.exists()  # look before overwriting; report which happened
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_capture_png(driver, element))
        emit(f"baseline {'updated' if existed else 'created'}: {baseline_path}",
             baseline=baseline_path, updated=existed, target=ref)
        return

    base_path = Path(baseline_path)
    if not base_path.exists():
        raise CommandError(f"no baseline at {baseline_path}; capture one with --update",
                           code=2, baseline=baseline_path)

    vd = _load_visualdiff()
    baseline_img = vd.open_image(str(base_path))

    deadline = time.monotonic() + args.timeout
    result = None
    while True:
        current = vd.open_image(_capture_png(driver, element))
        try:
            result = vd.compare(baseline_img, current, args.pixel_threshold)
        except vd.SizeMismatch as exc:  # never resize a golden — bail, don't poll
            raise CommandError(str(exc), code=2, baseline=baseline_path,
                               expected=list(exc.baseline), actual=list(exc.current)) from exc
        if result.ratio <= args.threshold:
            region = list(result.region) if result.region else None
            emit(f"{_target(ref)} matches {baseline_path} ({_pct(result.ratio)} differ)",
                 baseline=baseline_path, score=result.ratio, differing=result.differing,
                 threshold=args.threshold, region=region)
            return
        if time.monotonic() >= deadline:
            break
        time.sleep(_POLL)

    diffs = config.diffs_dir()
    diffs.mkdir(parents=True, exist_ok=True)
    diff_path = diffs / f"{base_path.stem}.diff.png"
    vd.write_diff(baseline_img, result, diff_path)
    region = list(result.region) if result.region else None
    where = f" region {result.region}" if result.region else ""
    raise CommandError(
        f"{_target(ref)} differs from {baseline_path}: {_pct(result.ratio)} > "
        f"{_pct(args.threshold)} threshold; diff -> {diff_path}{where}",
        code=1, baseline=baseline_path, score=result.ratio, threshold=args.threshold,
        differing=result.differing, region=region, diff=str(diff_path),
    )


def _capture_png(driver, element) -> bytes:  # noqa: ANN001
    return element.screenshot_as_png if element is not None else driver.get_screenshot_as_png()


def _resolve_single(driver, locator, ref: str):  # noqa: ANN001
    """Exactly one element to screenshot, else exit 2 (can't produce a stable image)."""
    matches = driver.find_elements(by=locator.by, value=locator.value)
    if not matches:
        raise CommandError(f"cannot screenshot {ref}: absent; run `snapshot` again", code=2)
    if len(matches) > 1:
        raise CommandError(f"cannot screenshot {ref}: {_ambiguous(matches)}", code=2)
    return matches[0]


def _load_visualdiff():
    try:
        from appium_pilot import visualdiff
    except ImportError as exc:
        raise CommandError(
            "visual diff needs Pillow — install with: pip install 'appium-pilot[visual]'",
            code=2,
        ) from exc
    return visualdiff


def _target(ref: str | None) -> str:
    return ref if ref else "screen"


def _pct(ratio: float) -> str:
    return f"{ratio * 100:.2f}%"


# --- batch (--all) ---------------------------------------------------------

@dataclass
class _Check:
    line_no: int
    text: str                       # the raw line, for messages when it won't parse
    ref: str | None = None
    kind: str | None = None
    expected: str | None = None
    locator: object | None = None   # None ⇒ the check has a terminal result (won't be polled)
    result: "Match | None" = None


def _run_batch(session: Session, args) -> None:
    lines = _read_lines(args.all_file)
    checks = _parse_checks(session, lines)
    if not checks:
        raise CommandError(f"no checks found in {args.all_file}", code=2)

    driver = session.attach()
    driver.implicitly_wait(0)
    strategy = session.strategy

    # Shared budget: each tick re-checks only the not-yet-passed lines; a pass sticks.
    pollable = [c for c in checks if c.locator is not None]
    for c in pollable:
        c.result = Match(False, "not evaluated")
    if pollable:
        deadline = time.monotonic() + args.timeout
        while True:
            active = [c for c in pollable if not c.result.ok]
            if not active:
                break
            for c in active:
                matches = driver.find_elements(by=c.locator.by, value=c.locator.value)
                c.result = evaluate(strategy, c.kind, c.expected, matches)
            if all(c.result.ok for c in pollable) or time.monotonic() >= deadline:
                break
            time.sleep(_POLL)

    _report_batch(checks)


def _parse_checks(session: Session, lines: list[str]) -> list[_Check]:
    """Turn raw lines into checks. Blank/`#` lines are skipped; a line that won't
    parse (bad syntax, per-line --timeout, unknown ref) becomes a terminal ERROR
    rather than aborting the whole batch."""
    parser = _line_parser()
    checks: list[_Check] = []
    for line_no, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        c = _Check(line_no, text)
        try:
            ns = parser.parse_args(shlex.split(text))
            c.ref = ns.ref
            c.kind, c.expected = _selected_matcher(ns)  # group is required here → never None
            c.locator = session.locator_for(c.ref)      # unknown ref → CommandError
        except _LineError as exc:
            c.result = Match(False, f"parse error: {exc}", evaluable=False)
        except ValueError as exc:  # shlex: unbalanced quotes
            c.result = Match(False, f"parse error: {exc}", evaluable=False)
        except CommandError as exc:
            c.result = Match(False, str(exc), evaluable=False)
        checks.append(c)
    return checks


def _report_batch(checks: list[_Check]) -> None:
    details = [{
        "line": c.line_no, "ref": c.ref, "check": c.kind, "ok": c.result.ok,
        "expected": c.expected, "actual": c.result.actual, "status": _status(c.result),
    } for c in checks]
    total = len(checks)
    n_pass = sum(1 for c in checks if c.result.ok)
    n_fail = sum(1 for c in checks if not c.result.ok and c.result.evaluable)
    n_err = total - n_pass - n_fail

    if not n_fail and not n_err:
        emit(f"{n_pass}/{total} checks passed", passed=n_pass, total=total, checks=details)
        return

    # Show only what didn't pass; --json still carries every result.
    bad = "\n".join(f"  {_status(c.result).upper()} {_check_desc(c)}"
                    for c in checks if not c.result.ok)
    raise CommandError(
        f"{n_fail + n_err}/{total} checks failed\n{bad}",
        code=_batch_code([c.result for c in checks]),
        passed=n_pass, failed=n_fail, errored=n_err, total=total, checks=details,
    )


def _batch_code(results: list[Match]) -> int:
    """Overall exit: a real failure (1) outranks an unevaluable check (2)."""
    if all(r.ok for r in results):
        return 0
    if any(not r.ok and r.evaluable for r in results):
        return 1
    return 2


class _LineError(Exception):
    """A batch line failed to parse (raised in place of argparse's sys.exit)."""


class _LineParser(argparse.ArgumentParser):
    def error(self, message: str):  # don't exit the process on a bad line
        raise _LineError(message)


def _line_parser() -> _LineParser:
    # Same matcher grammar as `expect`, but ref is mandatory and there is no
    # --timeout: batch timing is the invocation's job, so a per-line --timeout
    # falls through to "unrecognized arguments" → a clear per-line error.
    p = _LineParser(prog="expect", add_help=False)
    p.add_argument("ref")
    _add_matcher_group(p, required=True)
    return p


def _read_lines(source: str) -> list[str]:
    if source == "-":
        return sys.stdin.read().splitlines()
    try:
        return Path(source).read_text().splitlines()
    except OSError as exc:
        raise CommandError(f"cannot read checks file {source!r}: {exc}", code=2) from exc


# --- matcher engine (shared by single + batch) -----------------------------

@dataclass
class Match:
    """Outcome of one matcher evaluation.

    `evaluable=False` means the assertion could not be judged at all (ambiguous
    ref, non-checkable element, bad regex) → exit 2, distinct from a plain
    failed assertion → exit 1.
    """

    ok: bool
    actual: str  # human-readable observed state, for the failure message
    evaluable: bool = True


def evaluate(strategy, kind: str, expected: str | None, matches: list) -> Match:  # noqa: ANN001
    """Judge `kind` against the elements the locator currently resolves to."""
    # Presence matchers tolerate 0 or many matches — they count, not identify.
    if kind == "gone":
        return Match(True, "gone") if not _any_displayed(matches) else Match(False, "visible")
    if kind == "visible":
        if len(matches) > 1:
            return Match(False, _ambiguous(matches), evaluable=False)
        if not matches:
            return Match(False, "absent")
        return Match(True, "visible") if _displayed(matches[0]) else Match(False, "present, not displayed")

    # Everything below needs exactly one element to reason about.
    if not matches:
        return Match(False, "absent")
    if len(matches) > 1:
        return Match(False, _ambiguous(matches), evaluable=False)
    el = matches[0]

    if kind in ("text", "contains", "matches", "value"):
        fields = {"value": _VALUE_FIELDS, "text": _LABEL_FIELDS}.get(kind, _ANY_FIELDS)
        state = strategy.element_state(el)
        values = [state[k] for k in fields if isinstance(state.get(k), str) and state[k]]
        actual = " | ".join(values)
        if kind == "matches":
            try:
                rx = re.compile(expected)
            except re.error as exc:
                return Match(False, f"invalid regex {expected!r}: {exc}", evaluable=False)
            ok = any(rx.search(v) for v in values)
        elif kind == "contains":
            ok = any(expected in v for v in values)
        else:  # text / value — exact
            ok = any(v == expected for v in values)
        return Match(ok, actual)

    if kind in ("enabled", "disabled"):
        enabled = el.is_enabled()
        return Match(enabled == (kind == "enabled"), "enabled" if enabled else "disabled")

    if kind in ("checked", "unchecked"):
        state = strategy.is_checked(el)
        if state is None:
            return Match(False, "not a checkable element", evaluable=False)
        return Match(state == (kind == "checked"), "checked" if state else "unchecked")

    return Match(False, f"unknown matcher {kind!r}", evaluable=False)  # defensive; parser guards this


def _selected_matcher(args) -> tuple[str, str | None] | None:
    """The chosen matcher as (kind, expected-or-None), or None if none was given."""
    baseline = getattr(args, "baseline", None)  # absent on batch-line namespaces
    if baseline is not None:
        return "baseline", baseline
    for kind in _STRING_MATCHERS:
        value = getattr(args, kind)
        if value is not None:
            return kind, value
    for kind in _FLAG_MATCHERS:
        if getattr(args, kind):
            return kind, None
    return None


def _status(result: Match) -> str:
    if result.ok:
        return "pass"
    return "fail" if result.evaluable else "error"


def _displayed(el) -> bool:  # noqa: ANN001
    try:
        return el.is_displayed()
    except Exception:  # noqa: BLE001 — an element we can't query is, for our purposes, not shown
        return False


def _any_displayed(matches: list) -> bool:
    return any(_displayed(el) for el in matches)


def _ambiguous(matches: list) -> str:
    return f"ref is ambiguous ({len(matches)} matches); run `snapshot` again"


def _ok_message(ref: str, kind: str, expected: str | None) -> str:
    if kind in ("text", "value"):
        return f"{ref} {kind} == {expected!r}"
    if kind == "contains":
        return f"{ref} contains {expected!r}"
    if kind == "matches":
        return f"{ref} matches /{expected}/"
    return f"{ref} {kind}"


def _fail_message(ref: str, kind: str, expected: str | None, actual: str,
                  timeout: float | None = None) -> str:
    waited = f" (waited {timeout:g}s)" if timeout is not None else ""
    if kind in ("text", "value"):
        return f"{ref} {kind} != {expected!r}; got {actual!r}{waited}"
    if kind == "contains":
        return f"{ref} does not contain {expected!r}; got {actual!r}{waited}"
    if kind == "matches":
        return f"{ref} does not match /{expected}/; got {actual!r}{waited}"
    return f"{ref} not {kind}; is {actual}{waited}"


def _check_desc(c: _Check) -> str:
    """One line's outcome, for the batch failure report."""
    if c.kind is None:  # never parsed
        return f"line {c.line_no}: {c.result.actual}"
    if not c.result.evaluable:
        return f"{c.ref}: {c.result.actual}"
    return _fail_message(c.ref, c.kind, c.expected, c.result.actual)
