"""`find` text matching (§3): fixture-driven, no device.

`find` reuses the snapshot spine (`build_nodes`), so the coverage that matters is
the pure matching logic (`match_query`), the flat rendering (`render_matches`),
and each platform's `searchable_text` — plus the invariant that `find` numbers
refs exactly as `snapshot` does.
"""

import argparse
from pathlib import Path

import pytest

from appium_pilot.commands.find_cmd import match_query, run
from appium_pilot.output import CommandError
from appium_pilot.snapshot import build_nodes, build_snapshot, render_matches
from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")
FIXTURES = Path(__file__).parent.parent / "fixtures"


def _nodes(fixture: str, strategy):
    src = (FIXTURES / fixture).read_text()
    nodes, _ = build_nodes(src, strategy)
    return nodes


# --- searchable_text (the visible-label field set per platform) ------------

def test_android_searchable_joins_text_and_desc():
    assert AND.searchable_text({"text": "Save", "desc": "save button"}) == "Save save button"
    assert AND.searchable_text({"text": "Save"}) == "Save"
    assert AND.searchable_text({"id": "row", "clickable": "true"}) == ""


def test_ios_searchable_joins_name_label_value():
    assert IOS.searchable_text({"name": "n", "label": "l", "value": "v"}) == "n l v"
    assert IOS.searchable_text({"value": "42"}) == "42"
    assert IOS.searchable_text({}) == ""


# --- match_query: substring, case, ordering --------------------------------

def test_match_is_case_insensitive_substring_by_default():
    nodes = _nodes("android_source.xml", AND)
    # "text" matches the "Text" row (capital T) case-insensitively.
    matches = match_query(nodes, AND, "text", case_sensitive=False)
    assert [n.attrs.get("text") for n in matches] == ["Text"]
    # A partial substring still matches ("iew" ⊂ "Views").
    assert [n.attrs.get("text") for n in match_query(nodes, AND, "iew", False)] == ["Views"]


def test_case_sensitive_flag_respects_case():
    nodes = _nodes("android_source.xml", AND)
    assert match_query(nodes, AND, "text", case_sensitive=True) == []
    assert [n.attrs.get("text") for n in match_query(nodes, AND, "Text", True)] == ["Text"]


def test_no_match_returns_empty():
    nodes = _nodes("android_source.xml", AND)
    assert match_query(nodes, AND, "nonexistent-zzz", False) == []


def test_multiple_matches_in_document_order():
    nodes = _nodes("ios_source.xml", IOS)
    # Both "Query" and "Query Clear" contain "query"; document order is preserved.
    matches = match_query(nodes, IOS, "query", case_sensitive=False)
    assert len(matches) == 2
    refs = [n.ref for n in matches]
    assert refs == sorted(refs, key=lambda r: int(r[1:]))


# --- ref-numbering parity with snapshot ------------------------------------

@pytest.mark.parametrize("fixture,strategy", [
    ("android_source.xml", AND),
    ("ios_source.xml", IOS),
])
def test_find_refs_match_full_snapshot_numbering(fixture, strategy):
    src = (FIXTURES / fixture).read_text()
    nodes, refmap = build_nodes(src, strategy)
    xml, snap_refmap = build_snapshot(src, strategy)
    # Same spine → identical refmap; a matched ref is the ref snapshot would show.
    assert list(refmap) == list(snap_refmap)
    for n in nodes:
        assert n.ref in snap_refmap


# --- render_matches: flat, self-closing, ref-addressable -------------------

def test_render_matches_is_flat_and_ref_addressable():
    nodes = _nodes("android_source.xml", AND)
    matches = match_query(nodes, AND, "text", case_sensitive=False)
    out = render_matches(matches)
    lines = out.splitlines()
    assert len(lines) == 1  # one line per match, no nesting
    assert lines[0].lstrip().startswith("<")
    assert 'ref="e3"' in lines[0]
    assert lines[0].rstrip().endswith("/>")  # self-closing, no children


def test_render_matches_drops_children_of_matched_container():
    # A matched clickable row must print as one self-closing line even if it had
    # kept descendants — the tree relationship is meaningless in a filtered result.
    nodes = _nodes("ios_source.xml", IOS)
    matches = match_query(nodes, IOS, "query", case_sensitive=False)
    out = render_matches(matches)
    assert all(line.rstrip().endswith("/>") for line in out.splitlines())
    assert "</" not in out


# --- run() guards ----------------------------------------------------------

def test_empty_query_is_rejected_before_touching_a_session():
    # The guard runs before Session.load, so no session/driver is needed.
    args = argparse.Namespace(query="   ", case_sensitive=False, session="default")
    with pytest.raises(CommandError) as exc:
        run(args)
    assert exc.value.code == 2
