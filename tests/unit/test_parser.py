"""CLI parser: all subcommands registered, -s= normalization, error exit."""

import argparse

import pytest

from appium_pilot.cli import _normalize_session_flag, build_parser

EXPECTED = {
    "open", "close", "snapshot", "source", "screenshot", "tap", "type", "clear",
    "swipe", "scroll", "press", "hide-keyboard", "wait", "alert", "video-start", "video-stop",
    "launch", "activate", "terminate", "background", "install", "remove", "reset",
    "orientation", "devices", "list", "close-all", "kill-all", "skills", "doctor",
}


def _subcommand_names(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_all_subcommands_registered():
    assert EXPECTED <= _subcommand_names(build_parser())


@pytest.mark.parametrize("argv", [
    ["snapshot"], ["tap", "e1"], ["type", "e1", "hi"], ["swipe", "up"],
    ["video-start"], ["skills", "install"], ["orientation"], ["wait", "e1"],
    ["alert"], ["alert", "accept"], ["alert", "dismiss"],
])
def test_known_commands_parse(argv):
    args = build_parser().parse_args(argv)
    assert hasattr(args, "func")


def test_session_flag_normalization():
    assert _normalize_session_flag(["-s=foo", "tap", "e1"]) == ["--session", "foo", "tap", "e1"]
    assert _normalize_session_flag(["--session=bar", "list"]) == ["--session", "bar", "list"]
    assert _normalize_session_flag(["tap", "e1"]) == ["tap", "e1"]


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["not-a-command"])
