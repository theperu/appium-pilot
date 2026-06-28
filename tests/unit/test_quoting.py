"""XPath (_q) and NSPredicate (_pq) literal quoting, incl. embedded quotes."""

from appium_pilot.strategies.android import _q
from appium_pilot.strategies.ios import _pq


def test_q_simple_single_quotes():
    assert _q("Views") == "'Views'"


def test_q_apostrophe_switches_to_double_quotes():
    assert _q("O'Brien") == '"O\'Brien"'


def test_q_both_quotes_uses_concat():
    out = _q("it's \"x\"")
    assert out.startswith("concat(")


def test_pq_simple():
    assert _pq("Done") == "'Done'"


def test_pq_escapes_apostrophe():
    assert _pq("O'Brien") == "'O\\'Brien'"
