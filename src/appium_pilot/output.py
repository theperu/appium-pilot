"""Output contract: concise text by default, structured JSON with --json.

Commands report results through these helpers so the agent-facing contract is
defined in exactly one place: confirmations + state hints on stdout, errors on
stderr with a nonzero exit code.
"""

from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

# Set once by the CLI front-end from the global --json flag.
JSON_MODE = False


def set_json_mode(enabled: bool) -> None:
    global JSON_MODE
    JSON_MODE = enabled


def json_mode() -> bool:
    """Live accessor — import this, not the JSON_MODE value (which binds at import)."""
    return JSON_MODE


def emit(message: str, **data: Any) -> None:
    """Report success. `message` is the human one-liner; `data` is the JSON payload."""
    if JSON_MODE:
        print(json.dumps({"ok": True, "message": message, **data}))
    else:
        print(message)


def raw(text: str) -> None:
    """Print payload text verbatim (e.g. a snapshot's XML), no JSON wrapping."""
    if JSON_MODE:
        print(json.dumps({"ok": True, "data": text}))
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def fail(message: str, code: int = 1, **data: Any) -> NoReturn:
    """Report an error to stderr and exit nonzero."""
    if JSON_MODE:
        print(json.dumps({"ok": False, "error": message, **data}), file=sys.stderr)
    else:
        print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


class CommandError(Exception):
    """Raised by command handlers; the CLI front-end turns it into fail()."""

    def __init__(self, message: str, code: int = 1, **data: Any):
        super().__init__(message)
        self.code = code
        self.data = data
