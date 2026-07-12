"""`expect` matcher engine (§1.1), driven by fake WebElements.

The command layer only polls + formats; all the judging lives in
`evaluate()` and the per-platform `is_checked()`, so coverage sits there.
`evaluable=False` outcomes are what the CLI turns into exit 2 (can't judge)
rather than exit 1 (assertion failed).
"""

import argparse
import shlex

import pytest

from appium_pilot.commands import expect_cmd
from appium_pilot.commands.expect_cmd import (
    Match,
    _batch_code,
    _line_parser,
    _LineError,
    _read_lines,
    _selected_matcher,
    _status,
    evaluate,
)
from appium_pilot.output import CommandError
from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")


class _El:
    def __init__(self, text="", attrs=None, enabled=True, displayed=True):
        self.text = text
        self._attrs = attrs or {}
        self._enabled = enabled
        self._displayed = displayed

    def get_attribute(self, name):
        return self._attrs.get(name)

    def is_enabled(self):
        return self._enabled

    def is_displayed(self):
        return self._displayed


# --- text / value matching (exact, contains, regex) ------------------------

def test_text_exact_pass_and_fail():
    el = _El(text="Welcome")
    assert evaluate(AND, "text", "Welcome", [el]).ok
    miss = evaluate(AND, "text", "Wel", [el])  # exact, not substring
    assert not miss.ok and miss.actual == "Welcome"


def test_contains_is_substring():
    el = _El(text="Welcome back")
    assert evaluate(AND, "contains", "come ba", [el]).ok
    assert not evaluate(AND, "contains", "goodbye", [el]).ok


def test_matches_is_regex_and_bad_regex_is_unevaluable():
    el = _El(text="order-4821")
    assert evaluate(AND, "matches", r"order-\d+$", [el]).ok
    bad = evaluate(AND, "matches", "order-[", [el])
    assert not bad.ok and not bad.evaluable  # → exit 2, not a failed assertion


def test_value_matches_ios_value_field():
    # iOS keeps typed contents in `value`; --value must read it, not the label.
    el = _El(attrs={"label": "IntegerA", "value": "246", "name": "IntegerA"})
    assert evaluate(IOS, "value", "246", [el]).ok
    # --text is precise: it sees the label, not the contents.
    assert not evaluate(IOS, "text", "246", [el]).ok
    assert evaluate(IOS, "text", "IntegerA", [el]).ok


def test_contains_and_matches_search_value_too():
    # The fuzzy matchers look everywhere visible, so typed iOS contents (in
    # `value`) are reachable even though --text (label-only) wouldn't see them.
    el = _El(attrs={"label": "IntegerA", "value": "246"})
    assert evaluate(IOS, "contains", "24", [el]).ok
    assert evaluate(IOS, "matches", r"^\d+$", [el]).ok
    assert evaluate(IOS, "contains", "Integer", [el]).ok  # still finds the label


def test_value_matches_android_text_field():
    el = _El(text="hello")
    assert evaluate(AND, "value", "hello", [el]).ok


# --- presence: visible / gone ----------------------------------------------

def test_visible_requires_single_displayed_element():
    assert evaluate(AND, "visible", None, [_El(displayed=True)]).ok
    absent = evaluate(AND, "visible", None, [])
    assert not absent.ok and absent.actual == "absent" and absent.evaluable
    hidden = evaluate(AND, "visible", None, [_El(displayed=False)])
    assert not hidden.ok and "not displayed" in hidden.actual


def test_gone_passes_on_absent_or_hidden():
    assert evaluate(AND, "gone", None, []).ok
    assert evaluate(AND, "gone", None, [_El(displayed=False)]).ok
    shown = evaluate(AND, "gone", None, [_El(displayed=True)])
    assert not shown.ok and shown.actual == "visible"


# --- enabled / disabled ----------------------------------------------------

def test_enabled_disabled():
    assert evaluate(AND, "enabled", None, [_El(enabled=True)]).ok
    assert evaluate(AND, "disabled", None, [_El(enabled=False)]).ok
    assert not evaluate(AND, "enabled", None, [_El(enabled=False)]).ok


# --- checked / unchecked (tri-state; non-checkable is unevaluable) ---------

def test_android_checked_from_checkable():
    on = _El(attrs={"checkable": "true", "checked": "true"})
    off = _El(attrs={"checkable": "true", "checked": "false"})
    assert evaluate(AND, "checked", None, [on]).ok
    assert evaluate(AND, "unchecked", None, [off]).ok
    assert not evaluate(AND, "checked", None, [off]).ok


def test_ios_checked_from_switch_value():
    on = _El(attrs={"type": "XCUIElementTypeSwitch", "value": "1"})
    off = _El(attrs={"type": "XCUIElementTypeSwitch", "value": "0"})
    assert evaluate(IOS, "checked", None, [on]).ok
    assert evaluate(IOS, "unchecked", None, [off]).ok


def test_checked_on_non_checkable_is_unevaluable():
    plain = _El(text="Submit", attrs={"checkable": "false"})
    res = evaluate(AND, "checked", None, [plain])
    assert not res.ok and not res.evaluable and "not a checkable" in res.actual


# --- resolution edge cases -------------------------------------------------

def test_absent_fails_every_matcher_except_gone():
    assert not evaluate(AND, "text", "x", []).ok
    assert not evaluate(AND, "enabled", None, []).ok
    assert evaluate(AND, "gone", None, []).ok


def test_ambiguous_is_unevaluable_for_identity_matchers():
    two = [_El(text="a"), _El(text="a")]
    res = evaluate(AND, "text", "a", two)
    assert not res.ok and not res.evaluable and "ambiguous" in res.actual
    # gone still counts (both displayed) → fails but stays evaluable.
    gone = evaluate(AND, "gone", None, two)
    assert not gone.ok and gone.evaluable


# --- is_checked helper directly --------------------------------------------

def test_is_checked_none_when_not_checkable():
    assert AND.is_checked(_El(attrs={"checkable": "false"})) is None
    assert IOS.is_checked(_El(attrs={"type": "XCUIElementTypeButton"})) is None


# --- batch (--all): line grammar reuse + aggregation ------------------------

def _parse_line(text):
    return _line_parser().parse_args(shlex.split(text))


def test_batch_line_reuses_the_matcher_grammar():
    ns = _parse_line('e3 --text "Welcome back"')
    assert ns.ref == "e3" and _selected_matcher(ns) == ("text", "Welcome back")
    ns = _parse_line("e7 --gone")
    assert ns.ref == "e7" and _selected_matcher(ns) == ("gone", None)


def test_batch_line_requires_ref_and_one_matcher():
    with pytest.raises(_LineError):
        _parse_line("e3")                       # no matcher
    with pytest.raises(_LineError):
        _parse_line("--visible")                # no ref
    with pytest.raises(_LineError):
        _parse_line("e3 --text a --visible")    # two matchers


def test_batch_line_rejects_per_line_timeout():
    # Timing is the batch's job; a per-line --timeout is unrecognized here.
    with pytest.raises(_LineError):
        _parse_line("e3 --visible --timeout 2")


def test_status_classification():
    assert _status(Match(True, "visible")) == "pass"
    assert _status(Match(False, "absent")) == "fail"
    assert _status(Match(False, "ambiguous", evaluable=False)) == "error"


def test_batch_exit_code_precedence():
    ok, fail, err = Match(True, "x"), Match(False, "y"), Match(False, "z", evaluable=False)
    assert _batch_code([ok, ok]) == 0
    assert _batch_code([ok, fail]) == 1
    assert _batch_code([ok, err]) == 2
    # A real failure outranks an unevaluable one.
    assert _batch_code([fail, err]) == 1


def test_read_lines_from_file(tmp_path):
    p = tmp_path / "checks.txt"
    p.write_text("e1 --visible\n# comment\n\ne2 --gone\n")
    assert _read_lines(str(p)) == ["e1 --visible", "# comment", "", "e2 --gone"]


def test_read_lines_from_stdin(monkeypatch):
    import io
    monkeypatch.setattr(expect_cmd.sys, "stdin", io.StringIO("e1 --visible\ne2 --gone\n"))
    assert _read_lines("-") == ["e1 --visible", "e2 --gone"]


def test_read_lines_missing_file_is_code_2():
    with pytest.raises(CommandError) as exc:
        _read_lines("/no/such/checks/file.txt")
    assert exc.value.code == 2


# --- --baseline is recognised as a matcher (visual diff dispatch) ----------

def test_selected_matcher_detects_baseline():
    ns = argparse.Namespace(
        baseline="login.png", text=None, contains=None, matches=None, value=None,
        visible=False, gone=False, enabled=False, disabled=False, checked=False, unchecked=False,
    )
    assert _selected_matcher(ns) == ("baseline", "login.png")


def test_selected_matcher_baseline_absent_attr_is_safe():
    # Batch-line namespaces have no `baseline` attr; detection must not raise.
    ns = argparse.Namespace(
        text="Hi", contains=None, matches=None, value=None,
        visible=False, gone=False, enabled=False, disabled=False, checked=False, unchecked=False,
    )
    assert _selected_matcher(ns) == ("text", "Hi")
