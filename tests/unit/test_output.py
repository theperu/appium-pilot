"""Output contract: text vs --json, errors to stderr with nonzero exit."""

import argparse
import json

import pytest

from appium_pilot import config, output
from appium_pilot.commands import session_cmd


@pytest.fixture(autouse=True)
def _reset_json_mode():
    output.set_json_mode(False)
    yield
    output.set_json_mode(False)


def test_emit_text(capsys):
    output.emit("tapped e1", ref="e1")
    assert capsys.readouterr().out.strip() == "tapped e1"


def test_emit_json(capsys):
    output.set_json_mode(True)
    output.emit("tapped e1", ref="e1")
    assert json.loads(capsys.readouterr().out) == {"ok": True, "message": "tapped e1", "ref": "e1"}


def test_raw_text(capsys):
    output.raw("<node/>")
    assert capsys.readouterr().out.strip() == "<node/>"


def test_fail_text_exits_nonzero(capsys):
    with pytest.raises(SystemExit) as exc:
        output.fail("boom", code=2)
    assert exc.value.code == 2
    assert "boom" in capsys.readouterr().err


def test_fail_json_shape(capsys):
    output.set_json_mode(True)
    with pytest.raises(SystemExit):
        output.fail("boom", code=2, ref="e1")
    payload = json.loads(capsys.readouterr().err)
    assert payload["ok"] is False
    assert payload["error"] == "boom"
    assert payload["ref"] == "e1"


def test_commands_see_live_json_mode(tmp_path, monkeypatch, capsys):
    # Regression: commands must read JSON mode live, not import the value (which
    # binds at import time). `list --json` once silently emitted plain text.
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    output.set_json_mode(True)
    session_cmd.run_list(argparse.Namespace())
    assert json.loads(capsys.readouterr().out)["ok"] is True

