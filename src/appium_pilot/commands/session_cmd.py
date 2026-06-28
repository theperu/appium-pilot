"""Session management: `list`, `close`, `close-all`, `kill-all`."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess

from appium_pilot import config
from appium_pilot.output import emit, json_mode
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    ls = sub.add_parser("list", help="list active sessions")
    ls.set_defaults(func=run_list)

    cl = sub.add_parser("close", help="close a session (ends the server-side session)")
    cl.set_defaults(func=run_close)

    ca = sub.add_parser("close-all", help="close all sessions")
    ca.set_defaults(func=run_close_all)

    ka = sub.add_parser("kill-all", help="kill the Appium server and drop all session state")
    ka.set_defaults(func=run_kill_all)


def _session_names() -> list[str]:
    if not config.SESSIONS_DIR.exists():
        return []
    return sorted(p.stem for p in config.SESSIONS_DIR.glob("*.json"))


def run_list(args) -> None:
    names = _session_names()
    payload = []
    for name in names:
        try:
            s = Session.load(name)
            payload.append({"name": name, "platform": s.platform, "device": s.device,
                            "session_id": s.session_id})
        except Exception:  # noqa: BLE001
            payload.append({"name": name, "status": "unreadable"})
    if json_mode():
        emit(f"{len(names)} sessions", sessions=payload)
        return
    if not names:
        emit("no sessions")
        return
    for p in payload:
        print(f"{p.get('name'):12} {p.get('platform', '?'):8} {p.get('device', '?')}")


def _close_one(name: str) -> None:
    session = Session.load(name)
    try:
        session.attach().quit()  # ends the server-side session
    except Exception:  # noqa: BLE001 — session may already be dead; clean up regardless
        pass
    session.delete()


def run_close(args) -> None:
    _close_one(args.session)
    emit(f"closed session '{args.session}'", session=args.session)


def run_close_all(args) -> None:
    names = _session_names()
    for name in names:
        try:
            _close_one(name)
        except Exception:  # noqa: BLE001
            pass
    emit(f"closed {len(names)} sessions", count=len(names))


def run_kill_all(args) -> None:
    # Kill the managed Appium server, if we started it.
    killed = False
    if config.SERVER_FILE.exists():
        try:
            info = json.loads(config.SERVER_FILE.read_text())
            pid = info.get("pid")
            if pid:
                if os.name == "nt":
                    # Kill the whole tree; the node child outlives a bare terminate.
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                   capture_output=True)
                else:
                    os.kill(pid, signal.SIGTERM)
                killed = True
        except (ProcessLookupError, json.JSONDecodeError, OSError):
            pass
        config.SERVER_FILE.unlink(missing_ok=True)

    # Drop all session state.
    names = _session_names()
    for name in names:
        config.session_file(name).unlink(missing_ok=True)

    emit(
        f"killed server ({'stopped' if killed else 'not running'}) and dropped {len(names)} sessions",
        server_killed=killed,
        sessions_dropped=len(names),
    )
