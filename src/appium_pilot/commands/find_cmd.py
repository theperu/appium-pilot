"""`find` — return the refs of on-screen elements whose visible text matches.

A discovery affordance for when the agent already knows what it's looking for:
instead of re-emitting the whole screen with `snapshot`, `find "Login"` prints
just the matching lines. Matches are numbered exactly as a full `snapshot` would
number them (so `find` and `snapshot` never disagree on what `e7` is), and the
complete refmap is persisted — so the returned refs are immediately actionable
by `tap`/`type`/etc.

Read-only and view-only: it searches the current screen and never scrolls (use
`scroll --to-text` for that), so it's not a flow step.
"""

from __future__ import annotations

import argparse

from appium_pilot.output import CommandError, emit, raw
from appium_pilot.session import Session
from appium_pilot.snapshot import PNode, build_nodes, flatten, render_matches
from appium_pilot.strategies import PlatformStrategy


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("find", help="return refs of elements whose visible text matches a query")
    p.add_argument("query", help="text to match against elements' visible labels")
    p.add_argument("--case-sensitive", action="store_true",
                   help="match case exactly (default: case-insensitive)")
    p.set_defaults(func=run)


def match_query(
    nodes: list[PNode], strategy: PlatformStrategy, query: str, case_sensitive: bool
) -> list[PNode]:
    """Nodes whose visible text contains `query`, in document order.

    Substring match over each node's `searchable_text` (what the snapshot shows,
    post-fold). Case-insensitive unless `case_sensitive`.
    """
    needle = query if case_sensitive else query.lower()
    out: list[PNode] = []
    for node in flatten(nodes):
        hay = strategy.searchable_text(node.attrs)
        if not case_sensitive:
            hay = hay.lower()
        if needle in hay:
            out.append(node)
    return out


def run(args) -> None:
    if not args.query.strip():
        raise CommandError("find needs a non-empty query", code=2)

    session = Session.load(args.session)
    driver = session.attach()
    nodes, refmap = build_nodes(driver.page_source, session.strategy)
    # Persist the *full* screen refmap (not just matches) so every returned ref —
    # and any other visible ref — resolves for the next tap/type.
    session.set_refmap(refmap)
    session.save()

    matches = match_query(nodes, session.strategy, args.query, args.case_sensitive)

    if not matches:
        emit(
            f'no elements match "{args.query}" on the current screen; it may be '
            f'off-screen — try scroll --to-text "{args.query}"',
            count=0, query=args.query,
        )
        return

    raw(render_matches(matches))
