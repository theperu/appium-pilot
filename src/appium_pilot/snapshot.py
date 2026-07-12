"""Build the filtered-XML snapshot and the ref -> locator map.

We walk the live page source, keep only nodes the strategy deems meaningful,
collapse non-meaningful wrapper chains (their kept descendants bubble up to the
nearest kept ancestor), inject `ref` attributes, and serialize a compact XML.
Each kept node also records its best locator so later commands can re-find it.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from typing import Optional

from appium_pilot.strategies import Locator, PlatformStrategy


@dataclass
class PNode:
    ref: str
    tag: str
    attrs: dict
    xpath: str = ""  # unique indexed path; the collision-breaking fallback locator
    center: Optional[tuple[int, int]] = None  # pixel center, for --bounds
    children: list["PNode"] = field(default_factory=list)


def build_nodes(
    page_source: str, strategy: PlatformStrategy
) -> tuple[list[PNode], dict[str, Locator]]:
    """Walk the live page source into the filtered PNode tree + refmap.

    The shared spine of `snapshot` (which serializes the tree) and `find` (which
    filters it): both go through here so refs, folding, and dedupe are identical
    no matter which command built them — `e7` means the same element either way.
    """
    root = ET.fromstring(page_source)
    refmap: dict[str, Locator] = {}
    counter = [0]

    def walk(el: ET.Element, path: str) -> list[PNode]:
        node: Optional[PNode] = None
        if strategy.is_meaningful(el):
            counter[0] += 1
            ref = f"e{counter[0]}"
            xpath = path or f"/{strategy.effective_tag(el)}"
            # Expose the element's class/type to the strategy (iOS carries it as the
            # tag, not an attribute) so locators can disambiguate by type.
            attrs = dict(el.attrib)
            attrs.setdefault("type", strategy.effective_tag(el))
            refmap[ref] = strategy.best_locator(attrs, xpath)
            # Locator uses the full class (above); the emitted tag is shortened.
            tag = strategy.short_tag(strategy.effective_tag(el))
            node = PNode(ref=ref, tag=tag, attrs=strategy.kept_attrs(attrs), xpath=xpath,
                         center=strategy.center(attrs))

        child_nodes: list[PNode] = []
        sibling_counts: dict[str, int] = {}
        for child in list(el):
            ctag = strategy.effective_tag(child)
            sibling_counts[ctag] = sibling_counts.get(ctag, 0) + 1
            cpath = f"{path}/{ctag}[{sibling_counts[ctag]}]"
            child_nodes += walk(child, cpath)

        if node is not None:
            node.children = child_nodes
            return [node]
        return child_nodes  # collapse: bubble kept descendants up

    root_path = f"/{strategy.effective_tag(root)}"
    top = walk(root, root_path)
    _fold(top, strategy, refmap)
    refmap = _renumber(top, refmap)
    _dedupe(top, strategy, refmap)
    return top, refmap


def build_snapshot(
    page_source: str, strategy: PlatformStrategy, with_bounds: bool = False
) -> tuple[str, dict[str, Locator]]:
    """Return (filtered_xml, refmap). With `with_bounds`, each node also carries
    an ``at="cx,cy"`` pixel center (opt-in; costs tokens)."""
    top, refmap = build_nodes(page_source, strategy)
    xml = _serialize(top, with_bounds=with_bounds)
    return xml, refmap


def flatten(nodes: list[PNode]) -> list[PNode]:
    """Pre-order flatten of the PNode tree — `find` scans this to match refs."""
    out: list[PNode] = []
    for n in nodes:
        out.append(n)
        out.extend(flatten(n.children))
    return out


def render_matches(nodes: list[PNode]) -> str:
    """Serialize `find`'s matches as a flat list of self-closing lines.

    Children are dropped so a matched parent and a matched child each print as
    their own ref-addressable line; nesting is meaningless once the result is a
    filtered subset of the screen.
    """
    return _serialize([replace(n, children=[]) for n in nodes])


def _fold(nodes: list[PNode], strategy: PlatformStrategy, refmap: dict[str, Locator]) -> None:
    """Merge lone text leaves into their tappable parent (strategy.try_fold)."""
    for n in nodes:
        _fold(n.children, strategy, refmap)
        if len(n.children) == 1 and not n.children[0].children:
            child = n.children[0]
            keep = strategy.try_fold(n, child)
            if keep is not None:
                if keep == "child":
                    refmap[n.ref] = refmap[child.ref]
                del refmap[child.ref]
                n.children = []


def _renumber(nodes: list[PNode], refmap: dict[str, Locator]) -> dict[str, Locator]:
    """Re-assign e1..eN in document order after folding, keeping refs gap-free."""
    out: dict[str, Locator] = {}
    counter = [0]

    def visit(ns: list[PNode]) -> None:
        for n in ns:
            counter[0] += 1
            new_ref = f"e{counter[0]}"
            out[new_ref] = refmap[n.ref]
            n.ref = new_ref
            visit(n.children)

    visit(nodes)
    return out


def _dedupe(nodes: list[PNode], strategy: PlatformStrategy, refmap: dict[str, Locator]) -> None:
    """Break (by, value) collisions by falling back to each node's indexed xpath.

    best_locator can hand two refs the same locator (a list repeats a label or
    resource-id); that only surfaces as an "ambiguous, run snapshot again"
    failure at *action* time. Since the whole refmap is built here in one pass,
    detect the collision now and give each colliding ref its unique xpath — the
    display text is preserved for error messages. The emitted XML is unchanged.
    """
    flat: list[PNode] = []

    def collect(ns: list[PNode]) -> None:
        for n in ns:
            flat.append(n)
            collect(n.children)

    collect(nodes)

    groups: dict[tuple[str, str], list[PNode]] = {}
    for n in flat:
        loc = refmap[n.ref]
        groups.setdefault((loc.by, loc.value), []).append(n)

    for members in groups.values():
        if len(members) > 1:
            for n in members:
                refmap[n.ref] = strategy.xpath_locator(n.xpath, refmap[n.ref].text)


def _serialize(nodes: list[PNode], indent: int = 0, with_bounds: bool = False) -> str:
    lines: list[str] = []
    pad = "  " * indent
    for n in nodes:
        attr_str = "".join(f' {k}="{_esc(v)}"' for k, v in n.attrs.items())
        at = f' at="{n.center[0]},{n.center[1]}"' if with_bounds and n.center else ""
        open_tag = f'{pad}<{n.tag} ref="{n.ref}"{attr_str}{at}'
        if n.children:
            lines.append(open_tag + ">")
            lines.append(_serialize(n.children, indent + 1, with_bounds))
            lines.append(f"{pad}</{n.tag}>")
        else:
            lines.append(open_tag + "/>")
    return "\n".join(line for line in lines if line)


def _esc(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
