"""Flow record/replay (§2): step building, YAML round-trip, self-healing target
resolution, and replay outcome/exit-code mapping — all fixture-backed, no device.

Device-backed proof that replay actually drives the app lives in
tests/e2e/test_flow_e2e.py.
"""

from __future__ import annotations

import argparse

import pytest

from appium_pilot import config, record
from appium_pilot.commands import flow_cmd
from appium_pilot.output import CommandError
from appium_pilot.record import ReplayError, resolve_target
from appium_pilot.session import Session
from appium_pilot.strategies import Locator


# --- fakes -----------------------------------------------------------------

class FakeEl:
    def __init__(self, displayed=True, enabled=True):
        self._displayed, self._enabled = displayed, enabled
        self.clicked = self.cleared = False
        self.sent = None

    def is_displayed(self):
        return self._displayed

    def is_enabled(self):
        return self._enabled

    def click(self):
        self.clicked = True

    def clear(self):
        self.cleared = True

    def send_keys(self, text):
        self.sent = text


class FakeDriver:
    """find_elements is keyed by (by, value); action calls are recorded."""

    def __init__(self, by_value=None):
        self.by_value = by_value or {}
        self.activated, self.terminated = [], []
        self.orientation = None
        self.swiped = self.backgrounded = None

    def find_elements(self, by, value):
        return list(self.by_value.get((by, value), []))

    def implicitly_wait(self, _s):
        pass

    def activate_app(self, app):
        self.activated.append(app)

    def terminate_app(self, app):
        self.terminated.append(app)

    def swipe(self, *coords):
        self.swiped = coords

    def background_app(self, seconds):
        self.backgrounded = seconds


class FakeStrategy:
    """Records delegated calls; find_by_text/scroll_to_text are table-driven so
    self-healing paths are deterministic."""

    def __init__(self, by_text=None):
        self._by_text = by_text or {}
        self.calls = []

    def find_by_text(self, _driver, text):
        return self._by_text.get(text)

    def gesture_tap(self, _driver, kind, element=None, x=None, y=None, duration=1.0):
        self.calls.append(("gesture_tap", kind, element, x, y))

    def swipe(self, _driver, direction, amount):
        self.calls.append(("swipe", direction, amount))

    def submit(self, _driver, element):
        self.calls.append(("submit", element))

    def press_key(self, _driver, key):
        self.calls.append(("press_key", key))

    def hide_keyboard(self, _driver):
        self.calls.append(("hide_keyboard",))

    def scroll_to_element(self, _driver, element):
        self.calls.append(("scroll_to_element", element))

    def scroll_to_text(self, _driver, text):
        self.calls.append(("scroll_to_text", text))
        return self._by_text.get(text)

    def open_url(self, _driver, url, app_id):
        self.calls.append(("open_url", url, app_id))

    def accept_alert(self, _driver):
        self.calls.append(("accept_alert",))

    def dismiss_alert(self, _driver):
        self.calls.append(("dismiss_alert",))


@pytest.fixture
def sess_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    return tmp_path


def _session(**kw):
    base = dict(name="default", server_url="http://127.0.0.1:4723", session_id="sid",
                platform="android", device="emulator-5554",
                caps={"appium:appPackage": "com.x"})
    base.update(kw)
    return Session(**base)


def _ns(command, **kw):
    kw.setdefault("session", "default")
    return argparse.Namespace(command=command, **kw)


# --- step building (record._build_step) ------------------------------------

@pytest.fixture
def sess_with_ref():
    s = _session()
    s.set_refmap({"e1": Locator("accessibility id", "Views", "Views")})
    return s


def test_tap_by_ref_records_locator(sess_with_ref):
    step = record._build_step(
        _ns("tap", ref="e1", text=None, at=None, long=False, double=False, duration=1.0),
        sess_with_ref)
    assert step == {"action": "tap",
                    "locator": {"by": "accessibility id", "value": "Views", "text": "Views"}}


def test_tap_by_text_records_text_target(sess_with_ref):
    step = record._build_step(
        _ns("tap", ref=None, text="Login", at=None, long=False, double=False, duration=1.0),
        sess_with_ref)
    assert step == {"action": "tap", "text_target": "Login"}


def test_tap_at_and_long_mode(sess_with_ref):
    step = record._build_step(
        _ns("tap", ref=None, text=None, at="200,640", long=True, double=False, duration=2.0),
        sess_with_ref)
    assert step == {"action": "tap", "at": [200, 640], "mode": "long", "duration": 2.0}


def test_type_records_flags(sess_with_ref):
    step = record._build_step(
        _ns("type", ref="e1", text="hi", clear=True, submit=False), sess_with_ref)
    assert step == {"action": "type",
                    "locator": {"by": "accessibility id", "value": "Views", "text": "Views"},
                    "text": "hi", "clear": True}


def test_scroll_swipe_press_url(sess_with_ref):
    assert record._build_step(_ns("scroll", ref=None, to_text="Settings"), sess_with_ref) \
        == {"action": "scroll", "to_text": "Settings"}
    assert record._build_step(
        _ns("swipe", direction="up", coords=[], amount=0.5), sess_with_ref) \
        == {"action": "swipe", "direction": "up", "amount": 0.5}
    assert record._build_step(
        _ns("swipe", direction="coords", coords=[1, 2, 3, 4], amount=1.0), sess_with_ref) \
        == {"action": "swipe", "coords": [1, 2, 3, 4]}
    assert record._build_step(_ns("press", key="back"), sess_with_ref) \
        == {"action": "press", "key": "back"}
    assert record._build_step(_ns("url", url="app://x"), sess_with_ref) \
        == {"action": "url", "url": "app://x"}


def test_wait_variants(sess_with_ref):
    s = sess_with_ref
    assert record._build_step(_ns("wait", ref="e1", text=None, gone_ref=None, timeout=10.0), s) \
        == {"action": "wait",
            "locator": {"by": "accessibility id", "value": "Views", "text": "Views"},
            "timeout": 10.0}
    assert record._build_step(_ns("wait", ref=None, text="Done", gone_ref=None, timeout=5.0), s) \
        == {"action": "wait", "text": "Done", "timeout": 5.0}
    gone = record._build_step(_ns("wait", ref=None, text=None, gone_ref="e1", timeout=8.0), s)
    assert gone["action"] == "wait" and gone["gone_locator"]["value"] == "Views"


def test_alert_only_records_actions(sess_with_ref):
    assert record._build_step(_ns("alert", action="accept"), sess_with_ref) \
        == {"action": "alert", "alert_action": "accept"}
    # A bare `alert` (read) is not a flow step.
    assert record._build_step(_ns("alert", action=None), sess_with_ref) is None


def _expect_ns(ref, **matchers):
    fields = dict(ref=ref, text=None, contains=None, matches=None, value=None,
                  visible=False, gone=False, enabled=False, disabled=False,
                  checked=False, unchecked=False, baseline=None, all_file=None, timeout=5.0)
    fields.update(matchers)
    return _ns("expect", **fields)


def test_expect_records_matcher(sess_with_ref):
    step = record._build_step(_expect_ns("e1", value="hello"), sess_with_ref)
    assert step["action"] == "expect"
    assert step["matcher"] == {"kind": "value", "expected": "hello"}
    assert step["timeout"] == 5.0
    # Flag matcher → no `expected`.
    assert record._build_step(_expect_ns("e1", visible=True), sess_with_ref)["matcher"] \
        == {"kind": "visible"}


def test_expect_batch_and_baseline_not_recorded(sess_with_ref):
    assert record._build_step(_expect_ns("e1", all_file="checks.txt"), sess_with_ref) is None
    assert record._build_step(_expect_ns("e1", baseline="b.png"), sess_with_ref) is None


def test_lifecycle_and_orientation(sess_with_ref):
    assert record._build_step(_ns("reset"), sess_with_ref) == {"action": "reset"}
    assert record._build_step(_ns("background", seconds=3), sess_with_ref) \
        == {"action": "background", "seconds": 3}
    assert record._build_step(_ns("terminate", app_id=None), sess_with_ref) == {"action": "terminate"}
    assert record._build_step(_ns("orientation", value="landscape"), sess_with_ref) \
        == {"action": "orientation", "value": "landscape"}
    # Reading orientation is not a step.
    assert record._build_step(_ns("orientation", value=None), sess_with_ref) is None


def test_non_recordable_returns_none(sess_with_ref):
    assert record._build_step(_ns("get", ref="e1", attr=None), sess_with_ref) is None


# --- record_command: the cli.py hook (best-effort persistence) -------------

def test_record_command_appends_and_persists(sess_dir):
    s = _session()
    s.set_refmap({"e1": Locator("id", "com.x:id/go", "Go")})
    s.save()
    record.record_command(_ns("tap", ref="e1", text=None, at=None,
                              long=False, double=False, duration=1.0))
    assert Session.load("default").log == [
        {"action": "tap", "locator": {"by": "id", "value": "com.x:id/go", "text": "Go"}}]


def test_record_command_skips_readonly(sess_dir):
    s = _session()
    s.save()
    record.record_command(_ns("snapshot"))     # not in RECORDABLE
    record.record_command(_ns("get", ref="e1", attr=None))
    assert Session.load("default").log == []


def test_record_command_never_raises_on_bad_ref(sess_dir):
    s = _session()  # empty refmap → locator_for raises inside; must be swallowed
    s.save()
    record.record_command(_ns("tap", ref="e9", text=None, at=None,
                              long=False, double=False, duration=1.0))
    assert Session.load("default").log == []  # nothing recorded, no exception


# --- flow file I/O (YAML) --------------------------------------------------

def test_dump_load_roundtrip(sess_dir):
    s = _session()
    s.log = [{"action": "tap", "text_target": "Views"},
             {"action": "expect", "locator": {"by": "id", "value": "x", "text": ""},
              "matcher": {"kind": "visible"}, "timeout": 5.0}]
    text = record.dump_flow(s)
    assert "steps:" in text and "platform: android" in text
    (sess_dir / "f.yaml").write_text(text)
    doc = record.load_flow(str(sess_dir / "f.yaml"))
    assert doc["version"] == record.FLOW_VERSION
    assert doc["app"] == "com.x"
    assert doc["steps"] == s.log


def test_load_flow_rejects_bad_files(sess_dir):
    (sess_dir / "bad.yaml").write_text("just a string")
    with pytest.raises(CommandError) as e:
        record.load_flow(str(sess_dir / "bad.yaml"))
    assert e.value.code == 2
    with pytest.raises(CommandError) as e2:
        record.load_flow(str(sess_dir / "missing.yaml"))
    assert e2.value.code == 2


# --- self-healing target resolution ----------------------------------------

def test_resolve_primary_unique():
    el = FakeEl()
    drv = FakeDriver({("id", "v"): [el]})
    got, healed = resolve_target(drv, FakeStrategy(), {"locator": {"by": "id", "value": "v", "text": "T"}})
    assert got is el and healed is False


def test_resolve_heals_when_primary_absent():
    healed_el = FakeEl()
    drv = FakeDriver({("id", "v"): []})                       # primary gone
    strat = FakeStrategy(by_text={"T": healed_el})            # text still finds it
    got, healed = resolve_target(drv, strat, {"locator": {"by": "id", "value": "v", "text": "T"}})
    assert got is healed_el and healed is True


def test_resolve_heals_when_primary_ambiguous():
    healed_el = FakeEl()
    drv = FakeDriver({("id", "v"): [FakeEl(), FakeEl()]})     # 2 matches
    strat = FakeStrategy(by_text={"T": healed_el})
    got, healed = resolve_target(drv, strat, {"locator": {"by": "id", "value": "v", "text": "T"}})
    assert got is healed_el and healed is True


def test_resolve_fails_without_heal():
    drv = FakeDriver({("id", "v"): []})
    with pytest.raises(ReplayError):
        resolve_target(drv, FakeStrategy(), {"locator": {"by": "id", "value": "v", "text": ""}})


def test_resolve_text_target_and_coords():
    el = FakeEl()
    strat = FakeStrategy(by_text={"Go": el})
    assert resolve_target(FakeDriver(), strat, {"text_target": "Go"}) == (el, False)
    assert resolve_target(FakeDriver(), strat, {"at": [1, 2]}) == (None, False)
    with pytest.raises(ReplayError):
        resolve_target(FakeDriver(), strat, {"text_target": "Nope"})


# --- replay executor: per-step outcomes ------------------------------------

def test_run_step_tap_ok_and_healed():
    el = FakeEl()
    drv = FakeDriver({("id", "v"): [el]})
    strat = FakeStrategy()
    step = {"action": "tap", "locator": {"by": "id", "value": "v", "text": "T"}}
    out = flow_cmd._run_step(drv, strat, _session(), step)
    assert out["status"] == "ok" and el.clicked

    heal_el = FakeEl()
    drv2 = FakeDriver({("id", "v"): []})
    strat2 = FakeStrategy(by_text={"T": heal_el})
    out2 = flow_cmd._run_step(drv2, strat2, _session(), step)
    assert out2["status"] == "healed" and heal_el.clicked


def test_run_step_missing_target_is_error():
    drv = FakeDriver({("id", "v"): []})
    step = {"action": "tap", "locator": {"by": "id", "value": "v", "text": ""}}
    out = flow_cmd._run_step(drv, FakeStrategy(), _session(), step)
    assert out["status"] == "error" and "not found" in out["detail"]


def test_run_step_type_and_reset_and_url():
    el = FakeEl()
    drv = FakeDriver({("id", "v"): [el]})
    strat = FakeStrategy()
    sess = _session()
    flow_cmd._run_step(drv, strat, sess,
                       {"action": "type", "locator": {"by": "id", "value": "v", "text": ""},
                        "text": "hi", "clear": True})
    assert el.cleared and el.sent == "hi"

    flow_cmd._run_step(drv, strat, sess, {"action": "reset"})
    assert drv.terminated == ["com.x"] and drv.activated == ["com.x"]

    flow_cmd._run_step(drv, strat, sess, {"action": "url", "url": "app://p"})
    assert ("open_url", "app://p", "com.x") in strat.calls


def test_run_step_expect_pass_fail_error():
    visible, hidden = FakeEl(displayed=True), FakeEl(displayed=False)
    strat = FakeStrategy()
    ok = flow_cmd._run_step(
        FakeDriver({("id", "v"): [visible]}), strat, _session(),
        {"action": "expect", "locator": {"by": "id", "value": "v", "text": ""},
         "matcher": {"kind": "visible"}, "timeout": 0})
    assert ok["status"] == "ok"

    fail = flow_cmd._run_step(
        FakeDriver({("id", "v"): [hidden]}), strat, _session(),
        {"action": "expect", "locator": {"by": "id", "value": "v", "text": ""},
         "matcher": {"kind": "visible"}, "timeout": 0})
    assert fail["status"] == "fail" and "visible" in fail["detail"]

    # Ambiguous → cannot be evaluated → error (exit 2).
    err = flow_cmd._run_step(
        FakeDriver({("id", "v"): [FakeEl(), FakeEl()]}), strat, _session(),
        {"action": "expect", "locator": {"by": "id", "value": "v", "text": ""},
         "matcher": {"kind": "visible"}, "timeout": 0})
    assert err["status"] == "error"


# --- replay reporting → exit codes -----------------------------------------

def _results(*statuses):
    return [{"index": i, "action": "tap", "status": s, "detail": "", "desc": f"step{i}"}
            for i, s in enumerate(statuses, 1)]


def test_report_all_pass(capsys):
    flow_cmd._report(_results("ok", "healed", "ok"), total=3)  # no raise
    assert "replayed 3/3 steps (1 healed)" in capsys.readouterr().out


def test_report_failure_exit_1_outranks_error():
    with pytest.raises(CommandError) as e:
        flow_cmd._report(_results("ok", "error", "fail"), total=3)
    assert e.value.code == 1  # a real assertion failure outranks a structural error


def test_report_structural_error_exit_2():
    with pytest.raises(CommandError) as e:
        flow_cmd._report(_results("ok", "error"), total=5)
    assert e.value.code == 2 and e.value.data["errored"] == 1


# --- save / show / clear commands ------------------------------------------

def test_save_show_clear(sess_dir, capsys):
    s = _session()
    s.log = [{"action": "tap", "text_target": "Views"}]
    s.save()
    flow_cmd.run(_ns("flow", action="save", file=str(sess_dir / "f.yaml"), cont=False))
    assert "saved 1 steps" in capsys.readouterr().out
    assert (sess_dir / "f.yaml").exists()

    flow_cmd.run(_ns("flow", action="show", file=None, cont=False))
    assert "tap text 'Views'" in capsys.readouterr().out

    flow_cmd.run(_ns("flow", action="clear", file=None, cont=False))
    assert Session.load("default").log == []


def test_save_empty_log_errors(sess_dir):
    _session().save()
    with pytest.raises(CommandError) as e:
        flow_cmd.run(_ns("flow", action="save", file=str(sess_dir / "f.yaml"), cont=False))
    assert e.value.code == 2
