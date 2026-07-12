"""`flow` — record once, replay forever.

Every mutating command a session runs is logged (see record.py, wired in cli.py).
`flow save` dumps that log to a portable YAML file; `flow replay` re-runs it
against a live session, re-finding each element by the attributes captured at
snapshot time (never a stale `eN`) and self-healing to the display text when the
primary locator drifts. Recorded `expect` steps are re-checked, so a replay is a
regression test.

`flow replay` exit codes mirror `expect`:
  0  every step ran and every embedded assertion held
  1  an embedded assertion failed — the app is in the wrong state (a regression)
  2  a step could not be executed — target gone after healing, or driver refusal
     (the flow broke structurally; 1 outranks 2 when both occur under --continue)
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

from appium_pilot import config, record
from appium_pilot.output import CommandError, emit
from appium_pilot.record import ReplayError, resolve_target
from appium_pilot.session import Session

_POLL = 0.3  # seconds between assertion/wait polls, matching expect/wait


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("flow", help="record once, replay forever: save/replay/show/clear a flow")
    p.add_argument("action", choices=["save", "replay", "show", "clear"],
                   help="save/replay a FILE, show recorded steps, or clear the log")
    p.add_argument("file", nargs="?", help="flow file (required by save/replay; optional for show)")
    p.add_argument("--continue", dest="cont", action="store_true",
                   help="on replay, keep going after a failing step (best-effort)")
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    if args.action == "save":
        _save(session, args)
    elif args.action == "replay":
        _replay(session, args)
    elif args.action == "show":
        _show(session, args)
    else:  # clear
        _clear(session)


# --- save / show / clear ---------------------------------------------------

def _save(session: Session, args) -> None:
    if not args.file:
        raise CommandError("flow save needs a FILE (e.g. `flow save checkout.yaml`)")
    if not session.log:
        raise CommandError("nothing recorded yet — drive the app first, then save", code=2)
    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.dump_flow(session))
    emit(f"saved {len(session.log)} steps -> {args.file}", file=args.file, steps=len(session.log))


def _show(session: Session, args) -> None:
    steps = record.load_flow(args.file)["steps"] if args.file else session.log
    if not steps:
        emit("no steps recorded" if not args.file else "flow has no steps", steps=[])
        return
    lines = [f"{i}. {_describe(s)}" for i, s in enumerate(steps, 1)]
    emit("\n".join(lines), steps=steps, count=len(steps))


def _clear(session: Session) -> None:
    n = len(session.log)
    session.clear_log()
    session.save()
    emit(f"cleared {n} recorded steps", cleared=n)


# --- replay ----------------------------------------------------------------

def _replay(session: Session, args) -> None:
    if not args.file:
        raise CommandError("flow replay needs a FILE")
    doc = record.load_flow(args.file)
    steps = doc["steps"]
    if not steps:
        raise CommandError(f"{args.file} has no steps to replay", code=2)
    recorded = doc.get("platform")
    if recorded and recorded != session.platform:
        raise CommandError(
            f"flow was recorded on {recorded}, but session '{session.name}' is {session.platform}",
            code=2,
        )

    driver = session.attach()
    strategy = session.strategy
    stop = not args.cont
    results: list[dict] = []
    for i, step in enumerate(steps, 1):
        outcome = _run_step(driver, strategy, session, step)
        results.append({"index": i, "action": step.get("action"), **outcome})
        if outcome["status"] in ("fail", "error") and stop:
            break

    _report(results, len(steps))


def _run_step(driver, strategy, session: Session, step: dict) -> dict:  # noqa: ANN001
    desc = _describe(step)
    try:
        if step.get("action") == "expect":
            status, detail = _run_expect(driver, strategy, step)
        else:
            status = "healed" if _perform(driver, strategy, session, step) else "ok"
            detail = ""
    except ReplayError as exc:
        status, detail = "error", str(exc)
    except WebDriverException as exc:
        msg = (getattr(exc, "msg", None) or str(exc)).strip().splitlines()[0]
        status, detail = "error", f"driver error: {msg}"
    return {"status": status, "detail": detail, "desc": desc}


def _perform(driver, strategy, session: Session, step: dict) -> bool:  # noqa: ANN001
    """Execute one non-assertion step; return True if a target self-healed."""
    action = step["action"]

    if action == "tap":
        return _do_tap(driver, strategy, step)

    if action == "type":
        el, healed = resolve_target(driver, strategy, step)
        if step.get("clear"):
            el.clear()
        el.send_keys(step["text"])
        if step.get("submit"):
            strategy.submit(driver, el)
        return healed

    if action == "clear":
        el, healed = resolve_target(driver, strategy, step)
        el.clear()
        return healed

    if action == "scroll":
        if "to_text" in step:
            if strategy.scroll_to_text(driver, step["to_text"]) is None:
                raise ReplayError(f"could not scroll to text {step['to_text']!r}")
            return False
        el, healed = resolve_target(driver, strategy, step)
        strategy.scroll_to_element(driver, el)
        return healed

    if action == "swipe":
        if "coords" in step:
            x1, y1, x2, y2 = step["coords"]
            driver.swipe(x1, y1, x2, y2, 400)
        else:
            strategy.swipe(driver, step["direction"], step.get("amount", 1.0))
        return False

    if action == "press":
        strategy.press_key(driver, step["key"])
        return False

    if action == "hide_keyboard":
        strategy.hide_keyboard(driver)
        return False

    if action == "wait":
        return _do_wait(driver, strategy, step)

    if action == "url":
        strategy.open_url(driver, step["url"], session.app_id)
        return False

    if action == "alert":
        if step["alert_action"] == "accept":
            strategy.accept_alert(driver)
        else:
            strategy.dismiss_alert(driver)
        return False

    if action in ("launch", "activate"):
        driver.activate_app(_app(session, step))
        return False
    if action == "terminate":
        driver.terminate_app(_app(session, step))
        return False
    if action == "background":
        driver.background_app(step.get("seconds", -1))
        return False
    if action == "reset":
        app = _app(session, step)
        driver.terminate_app(app)
        driver.activate_app(app)
        return False
    if action == "orientation":
        driver.orientation = step["value"].upper()
        return False

    raise ReplayError(f"unknown action {action!r}")


def _do_tap(driver, strategy, step: dict) -> bool:  # noqa: ANN001
    mode = step.get("mode", "single")
    if "at" in step:
        x, y = step["at"]
        strategy.gesture_tap(driver, mode, x=x, y=y, duration=step.get("duration", 1.0))
        return False
    el, healed = resolve_target(driver, strategy, step)
    if mode == "single":
        el.click()
    else:
        strategy.gesture_tap(driver, mode, element=el, duration=step.get("duration", 1.0))
    return healed


def _do_wait(driver, strategy, step: dict) -> bool:  # noqa: ANN001
    timeout = step.get("timeout", 10.0)
    driver.implicitly_wait(0)  # explicit polling owns timing (mirrors wait_cmd)
    try:
        wait = WebDriverWait(driver, timeout=timeout, poll_frequency=_POLL)
        if "gone_locator" in step:
            loc = step["gone_locator"]
            wait.until_not(lambda d: d.find_elements(by=loc["by"], value=loc["value"]))
        elif "text" in step:
            wait.until(lambda d: strategy.find_by_text(d, step["text"]))
        else:
            loc = step["locator"]
            wait.until(lambda d: d.find_elements(by=loc["by"], value=loc["value"]))
    except TimeoutException as exc:
        raise ReplayError(f"wait timed out after {timeout:g}s") from exc
    finally:
        driver.implicitly_wait(config.IMPLICIT_WAIT)
    return False


def _run_expect(driver, strategy, step: dict) -> tuple[str, str]:  # noqa: ANN001
    """Re-check a recorded assertion. Returns (status, detail): ok / fail (wrong
    state) / error (couldn't evaluate)."""
    from appium_pilot.commands import expect_cmd

    loc = step["locator"]
    matcher = step["matcher"]
    kind, expected = matcher["kind"], matcher.get("expected")
    timeout = step.get("timeout", 5.0)

    driver.implicitly_wait(0)
    try:
        deadline = time.monotonic() + timeout
        result = expect_cmd.Match(False, "not evaluated")
        while True:
            matches = driver.find_elements(by=loc["by"], value=loc["value"])
            result = expect_cmd.evaluate(strategy, kind, expected, matches)
            if result.ok:
                return "ok", ""
            if time.monotonic() >= deadline:
                break
            time.sleep(_POLL)
    finally:
        driver.implicitly_wait(config.IMPLICIT_WAIT)

    if not result.evaluable:
        return "error", result.actual
    if expected is not None:
        return "fail", f"{kind} != {expected!r}; got {result.actual!r}"
    return "fail", f"not {kind}; is {result.actual}"


def _app(session: Session, step: dict) -> str:
    app_id = step.get("app_id") or session.app_id
    if not app_id:
        raise ReplayError("no app id known for this session")
    return app_id


# --- reporting -------------------------------------------------------------

_MARK = {"ok": "ok", "healed": "HEAL", "fail": "FAIL", "error": "ERR"}


def _report(results: list[dict], total: int) -> None:
    ran = len(results)
    n_pass = sum(1 for r in results if r["status"] in ("ok", "healed"))
    n_healed = sum(1 for r in results if r["status"] == "healed")
    n_fail = sum(1 for r in results if r["status"] == "fail")
    n_err = sum(1 for r in results if r["status"] == "error")
    body = "\n".join(
        f"  {_MARK[r['status']]} {r['desc']}" + (f" — {r['detail']}" if r["detail"] else "")
        for r in results
    )

    if not n_fail and not n_err:
        heal = f" ({n_healed} healed)" if n_healed else ""
        emit(f"replayed {n_pass}/{total} steps{heal}\n{body}",
             total=total, ran=ran, passed=n_pass, healed=n_healed, steps=results)
        return

    raise CommandError(
        f"flow failed at step {ran}/{total}\n{body}",
        code=1 if n_fail else 2,
        total=total, ran=ran, passed=n_pass, failed=n_fail, errored=n_err,
        healed=n_healed, steps=results,
    )


# --- step description (used by show + replay reporting) --------------------

def _describe(step: dict) -> str:
    a = step.get("action", "?")
    tgt = _target_desc(step)
    if a == "tap":
        mode = f" ({step['mode']})" if step.get("mode") else ""
        return f"tap {tgt}{mode}"
    if a == "type":
        return f"type {step.get('text')!r} into {tgt}"
    if a == "clear":
        return f"clear {tgt}"
    if a == "scroll":
        return f"scroll to {step['to_text']!r}" if "to_text" in step else f"scroll {tgt} into view"
    if a == "swipe":
        return f"swipe {','.join(map(str, step['coords']))}" if "coords" in step else f"swipe {step['direction']}"
    if a == "press":
        return f"press {step['key']}"
    if a == "hide_keyboard":
        return "hide keyboard"
    if a == "wait":
        if "gone_locator" in step:
            return f"wait until gone: {_loc_desc(step['gone_locator'])}"
        if "text" in step:
            return f"wait for text {step['text']!r}"
        return f"wait for {tgt}"
    if a == "url":
        return f"url {step['url']}"
    if a == "alert":
        return f"alert {step['alert_action']}"
    if a == "expect":
        return f"expect {tgt} {_matcher_desc(step['matcher'])}"
    if a in ("launch", "activate", "terminate"):
        return f"{a} {step.get('app_id') or 'app'}"
    if a == "background":
        return f"background {step.get('seconds')}s"
    if a == "reset":
        return "reset app"
    if a == "orientation":
        return f"orientation {step['value']}"
    return a


def _target_desc(step: dict) -> str:
    if "at" in step:
        return f"({step['at'][0]},{step['at'][1]})"
    if "text_target" in step:
        return f"text {step['text_target']!r}"
    if "locator" in step:
        return _loc_desc(step["locator"])
    return ""


def _loc_desc(loc: dict) -> str:
    return f"{loc['text']!r}" if loc.get("text") else f"{loc['by']}={loc['value']!r}"


def _matcher_desc(m: dict) -> str:
    kind = m["kind"]
    return f"{kind} {m['expected']!r}" if "expected" in m else kind
