"""E2E: `expect` as a test oracle (§1.1).

Reuses the scenario hooks (ready_ref / reach_editable / disappearing_ref) so the
same flows exercise both platforms. Exit codes are the contract under test:
0 held, 1 failed, 2 could-not-evaluate — so several cases assert on rc, not text.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_expect_visible_passes(fresh, app):
    ref = app.ready_ref(fresh)
    assert fresh.run("expect", ref, "--visible", check=False)[0] == 0


def test_expect_enabled_passes(fresh, app):
    ref = app.ready_ref(fresh)
    assert fresh.run("expect", ref, "--enabled", check=False)[0] == 0


def test_expect_value_reflects_typed_text(fresh, app):
    ref = app.reach_editable(fresh)
    fresh.run("type", ref, app.type_value, "--clear")
    # exact contents, a substring, and a non-empty regex — the three text paths.
    assert fresh.run("expect", ref, "--value", app.type_value, check=False)[0] == 0
    assert fresh.run("expect", ref, "--contains", app.type_value[:2], check=False)[0] == 0
    assert fresh.run("expect", ref, "--matches", ".+", check=False)[0] == 0


def test_expect_gone_after_disappear(fresh, app):
    ref = app.disappearing_ref(fresh)
    if not ref:
        pytest.skip("no disappearing element in this app's scenario")
    app.cause_disappear(fresh)
    # Polls until the ref stops resolving; a generous window absorbs the transition.
    assert fresh.run("expect", ref, "--gone", "--timeout", "8", check=False)[0] == 0


def test_expect_failed_assertion_exits_1(fresh, app):
    ref = app.ready_ref(fresh)
    rc, _out, err = fresh.run("expect", ref, "--text", "zzz-not-on-screen",
                              "--timeout", "1", check=False)
    assert rc == 1 and "zzz-not-on-screen" in err  # exact-match failure, app is "wrong"


def test_expect_disabled_on_enabled_exits_1(fresh, app):
    ref = app.ready_ref(fresh)
    assert fresh.run("expect", ref, "--disabled", "--timeout", "1", check=False)[0] == 1


def test_expect_checked_on_non_checkable_exits_2(fresh, app):
    # A non-toggle can't be judged checked/unchecked → exit 2, not a failed assert.
    ref = app.ready_ref(fresh)
    rc, _out, err = fresh.run("expect", ref, "--checked", "--timeout", "1", check=False)
    assert rc == 2 and "checkable" in err


# --- expect --all: soft-assertion batch (§1.2) -----------------------------

def test_expect_all_passes(fresh, app, tmp_path):
    ref = app.ready_ref(fresh)
    checks = tmp_path / "pass.checks"
    checks.write_text(f"# smoke\n{ref} --visible\n\n{ref} --enabled\n")  # comment + blank ignored
    rc, out, _ = fresh.run("expect", "--all", str(checks), check=False)
    assert rc == 0 and "2/2 checks passed" in out


def test_expect_all_collects_failures_and_errors(fresh, app, tmp_path):
    ref = app.ready_ref(fresh)
    checks = tmp_path / "mixed.checks"
    # one pass, one real failure (it's enabled), one unevaluable (unknown ref).
    checks.write_text(f"{ref} --visible\n{ref} --disabled\nnope99 --visible\n")
    rc, data = fresh.run("expect", "--all", str(checks), "--timeout", "1",
                         json_out=True, check=False)
    assert rc == 1  # a real failure outranks the unevaluable one
    assert (data["passed"], data["failed"], data["errored"], data["total"]) == (1, 1, 1, 3)
    assert {c["status"] for c in data["checks"]} == {"pass", "fail", "error"}


# --- expect --baseline: visual regression (§1.3) ---------------------------

def test_expect_baseline_update_then_match(fresh, app, tmp_path):
    ref = app.ready_ref(fresh)
    base = tmp_path / "ready.png"
    rc, out, _ = fresh.run("expect", ref, "--baseline", str(base), "--update", check=False)
    assert rc == 0 and base.exists() and "created" in out
    # Same static element, unchanged → within the default threshold.
    assert fresh.run("expect", ref, "--baseline", str(base), check=False)[0] == 0


def test_expect_baseline_detects_change(fresh, app, tmp_path):
    ref = app.reach_editable(fresh)
    base = tmp_path / "field.png"
    fresh.run("expect", ref, "--baseline", str(base), "--update")
    fresh.run("type", ref, app.type_value, "--clear")  # alters the field's pixels
    rc, data = fresh.run("expect", ref, "--baseline", str(base), "--timeout", "1",
                         json_out=True, check=False)
    assert rc == 1 and data["score"] > data["threshold"]
    assert Path(data["diff"]).exists()


def test_expect_baseline_missing_exits_2(fresh, tmp_path):
    rc, _out, err = fresh.run("expect", "--baseline", str(tmp_path / "nope.png"),
                              "--timeout", "1", check=False)
    assert rc == 2 and "update" in err
