"""The recording contract: turn a successful command into a ref-free step, and
re-find a step's target on replay. One place owns "what is recordable and how",
the way output.py owns the output contract.

A recorded step never stores an `eN` ref (those die at the next snapshot). It
stores the *locator* the ref resolved to at snapshot time — {by, value, text} —
so replay can re-find the element on a later run. `text` doubles as the
self-healing fallback when the primary locator no longer matches.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from appium_pilot.output import CommandError
from appium_pilot.session import Session

FLOW_VERSION = 1

# Commands worth recording as flow steps. Everything else (snapshot, find, get,
# open, session mgmt, devices, doctor, skills, video, capture) is read-only or
# meta and is skipped — including `flow` itself, so replay never re-records.
RECORDABLE = {
    "tap", "type", "clear", "scroll", "swipe", "press", "hide-keyboard",
    "wait", "url", "alert", "expect",
    "launch", "activate", "terminate", "background", "reset", "orientation",
}


class ReplayError(Exception):
    """A step could not be executed on replay (target gone, driver rejected it)."""


# --- recording (cli.py post-success hook) ----------------------------------

def record_command(args) -> None:  # noqa: ANN001
    """Append this just-succeeded command to the session log. Best-effort:
    never let a recording failure turn a successful action into an error."""
    if getattr(args, "command", None) not in RECORDABLE:
        return
    try:
        session = Session.load(args.session)
        step = _build_step(args, session)
        if step is not None:
            session.append_step(step)
            session.save()
    except Exception:  # noqa: BLE001 — recording is telemetry, not the action
        import os
        if os.environ.get("APPIUM_PILOT_DEBUG"):
            raise


def _build_step(args, session: Session) -> Optional[dict]:  # noqa: ANN001
    cmd = args.command

    if cmd == "tap":
        step = {"action": "tap", **_tap_target(args, session)}
        mode = "long" if args.long else "double" if args.double else "single"
        if mode != "single":
            step["mode"] = mode
            if mode == "long":
                step["duration"] = args.duration
        return step

    if cmd == "type":
        step = {"action": "type", "locator": _loc(session, args.ref), "text": args.text}
        if args.clear:
            step["clear"] = True
        if args.submit:
            step["submit"] = True
        return step

    if cmd == "clear":
        return {"action": "clear", "locator": _loc(session, args.ref)}

    if cmd == "scroll":
        if args.to_text:
            return {"action": "scroll", "to_text": args.to_text}
        return {"action": "scroll", "locator": _loc(session, args.ref)}

    if cmd == "swipe":
        if args.direction == "coords":
            return {"action": "swipe", "coords": list(args.coords)}
        return {"action": "swipe", "direction": args.direction, "amount": args.amount}

    if cmd == "press":
        return {"action": "press", "key": args.key}

    if cmd == "hide-keyboard":
        return {"action": "hide_keyboard"}

    if cmd == "wait":
        if args.gone_ref:
            return {"action": "wait", "gone_locator": _loc(session, args.gone_ref),
                    "timeout": args.timeout}
        if args.text:
            return {"action": "wait", "text": args.text, "timeout": args.timeout}
        return {"action": "wait", "locator": _loc(session, args.ref), "timeout": args.timeout}

    if cmd == "url":
        return {"action": "url", "url": args.url}

    if cmd == "alert":
        if args.action not in ("accept", "dismiss"):
            return None  # a bare `alert` read is not a flow step
        return {"action": "alert", "alert_action": args.action}

    if cmd == "expect":
        return _expect_step(args, session)

    if cmd in ("launch", "activate", "terminate"):
        step = {"action": cmd}
        if args.app_id:
            step["app_id"] = args.app_id
        return step

    if cmd == "background":
        return {"action": "background", "seconds": args.seconds}

    if cmd == "reset":
        return {"action": "reset"}

    if cmd == "orientation":
        if not args.value:
            return None  # reading orientation is not a flow step
        return {"action": "orientation", "value": args.value}

    return None


def _tap_target(args, session: Session) -> dict:  # noqa: ANN001
    if args.at:
        x, y = (int(p) for p in args.at.replace(" ", "").split(","))
        return {"at": [x, y]}
    if args.text:
        return {"text_target": args.text}
    return {"locator": _loc(session, args.ref)}


def _expect_step(args, session: Session) -> Optional[dict]:  # noqa: ANN001
    # Only the single-ref matcher form is a replayable assertion; --all and
    # --baseline are out of scope for v1 flow recording.
    from appium_pilot.commands import expect_cmd

    if args.all_file or getattr(args, "baseline", None):
        return None
    matcher = expect_cmd._selected_matcher(args)
    if matcher is None or not args.ref:
        return None
    kind, expected = matcher
    m: dict = {"kind": kind}
    if expected is not None:
        m["expected"] = expected
    return {"action": "expect", "locator": _loc(session, args.ref),
            "matcher": m, "timeout": args.timeout}


def _loc(session: Session, ref: str) -> dict:
    """The locator a ref pointed at, as a plain dict for the flow file."""
    return session.locator_for(ref).to_dict()


# --- flow file I/O ---------------------------------------------------------

def dump_flow(session: Session) -> str:
    """Serialize the session's recorded log to a YAML document."""
    import yaml

    doc = {
        "version": FLOW_VERSION,
        "platform": session.platform,
        "app": session.app_id,
        "steps": session.log,
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def load_flow(path: str) -> dict:
    """Read and validate a flow file. Raises CommandError on any problem."""
    import yaml

    p = Path(path)
    try:
        text = p.read_text()
    except OSError as exc:
        raise CommandError(f"cannot read flow {path!r}: {exc}", code=2) from exc
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CommandError(f"invalid YAML in {path!r}: {exc}", code=2) from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
        raise CommandError(f"{path!r} is not a flow file (missing 'steps' list)", code=2)
    return doc


# --- replay target resolution (self-healing) -------------------------------

def resolve_target(driver, strategy, step: dict):  # noqa: ANN001
    """Find the element a step targets, healing to the captured text if the
    primary locator drifted. Returns (element_or_None, healed). Coordinate steps
    return (None, False) — the caller acts on raw x,y. Raises ReplayError if the
    element cannot be found."""
    if "at" in step:
        return None, False
    if "text_target" in step:
        el = strategy.find_by_text(driver, step["text_target"])
        if el is None:
            raise ReplayError(f"no element with text {step['text_target']!r}")
        return el, False

    loc = step["locator"]
    matches = driver.find_elements(by=loc["by"], value=loc["value"])
    if len(matches) == 1:
        return matches[0], False

    # Self-heal: the recorded (by, value) is gone or now ambiguous — fall back to
    # the display text captured at record time before giving up.
    text = loc.get("text")
    if text:
        healed = strategy.find_by_text(driver, text)
        if healed is not None:
            return healed, True
    if not matches:
        raise ReplayError(f"target ({loc['by']}={loc['value']!r}) not found")
    raise ReplayError(f"target ({loc['by']}={loc['value']!r}) is ambiguous "
                      f"({len(matches)} matches)")
