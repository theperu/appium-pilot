"""`skills install` / `skills uninstall` — make the bundled skill discoverable by
AI coding agents.

The skill content ships inside the package (appium_pilot/skilldata/SKILL.md) and
is written into each agent's documented location:

- claude  -> ~/.claude/skills/appium-pilot/SKILL.md      (user-level)
- cursor  -> ./.cursor/rules/appium-pilot.mdc            (project)
- copilot -> ./.github/copilot-instructions.md           (project, managed block)
- agents  -> ./AGENTS.md                                 (project, managed block)

Agents then discover the commands and are pointed at `appium-pilot --help`.
"""

from __future__ import annotations

import argparse
import shutil
from importlib import resources
from pathlib import Path

from appium_pilot.output import CommandError, emit

NAME = "appium-pilot"
TOOLS = ("claude", "cursor", "copilot", "agents")
_BEGIN = f"<!-- BEGIN {NAME} skill -->"
_END = f"<!-- END {NAME} skill -->"


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("skills", help="install/uninstall the agent skill")
    actions = p.add_subparsers(dest="skills_action", required=True, metavar="<action>")
    for action, func, verb in (("install", run_install, "install"), ("uninstall", run_uninstall, "remove")):
        sp = actions.add_parser(action, help=f"{verb} the skill")
        sp.add_argument("--tool", choices=(*TOOLS, "all"), default="claude",
                        help="target agent (default: claude; 'all' for every supported tool)")
        sp.add_argument("--dir", help="base directory override (advanced; default: per-tool location)")
        sp.set_defaults(func=func)


# --- skill content ---------------------------------------------------------

def _bundled() -> str:
    try:
        return resources.files("appium_pilot").joinpath("skilldata/SKILL.md").read_text()
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise CommandError("bundled SKILL.md not found in the package") from exc


def _description_and_body() -> tuple[str, str]:
    """Split the SKILL.md frontmatter (for `description`) from its body."""
    text = _bundled()
    parts = text.split("---", 2)
    if len(parts) == 3:
        frontmatter, body = parts[1], parts[2].strip()
        desc = ""
        for line in frontmatter.splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
        return desc, body
    return "", text.strip()


# --- per-tool targets ------------------------------------------------------

def _targets(args) -> dict[str, Path]:
    base = Path(args.dir).expanduser() if args.dir else None
    claude_base = base or (Path.home() / ".claude" / "skills")
    proj = base or Path.cwd()
    paths = {
        "claude": claude_base / NAME / "SKILL.md",
        "cursor": proj / ".cursor" / "rules" / f"{NAME}.mdc",
        "copilot": proj / ".github" / "copilot-instructions.md",
        "agents": proj / "AGENTS.md",
    }
    chosen = TOOLS if args.tool == "all" else (args.tool,)
    return {t: paths[t] for t in chosen}


def _managed_block(body: str) -> str:
    return f"{_BEGIN}\n## {NAME} — mobile automation CLI\n\n{body}\n{_END}\n"


def _write_block(path: Path, body: str) -> None:
    existing = path.read_text() if path.exists() else ""
    block = _managed_block(body)
    if _BEGIN in existing and _END in existing:
        pre = existing.split(_BEGIN)[0].rstrip()
        post = existing.split(_END, 1)[1].lstrip()
        new = "\n\n".join(p for p in (pre, block.strip(), post) if p) + "\n"
    else:
        prefix = existing.rstrip() + "\n\n" if existing.strip() else ""
        new = prefix + block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new)


def _remove_block(path: Path) -> bool:
    if not path.exists():
        return False
    existing = path.read_text()
    if _BEGIN not in existing:
        return False
    pre = existing.split(_BEGIN)[0].rstrip()
    post = existing.split(_END, 1)[1].lstrip() if _END in existing else ""
    remaining = "\n\n".join(p for p in (pre, post) if p).strip()
    if remaining:
        path.write_text(remaining + "\n")
    else:
        path.unlink()  # the file held only our block
    return True


# --- commands --------------------------------------------------------------

def run_install(args) -> None:
    desc, body = _description_and_body()
    installed: list[str] = []
    for tool, path in _targets(args).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if tool == "claude":
            path.write_text(_bundled())
        elif tool == "cursor":
            path.write_text(f"---\ndescription: {desc}\nalwaysApply: false\n---\n\n{body}\n")
        else:  # copilot, agents — append a managed block to a shared file
            _write_block(path, body)
        installed.append(str(path))
    emit("installed skill -> " + ", ".join(installed), paths=installed)


def run_uninstall(args) -> None:
    removed: list[str] = []
    for tool, path in _targets(args).items():
        if tool == "claude":
            target = path.parent  # the appium-pilot/ skill dir
            if target.exists():
                shutil.rmtree(target)
                removed.append(str(target))
        elif tool == "cursor":
            if path.exists():
                path.unlink()
                removed.append(str(path))
        else:
            if _remove_block(path):
                removed.append(str(path))
    if removed:
        emit("removed skill from " + ", ".join(removed), paths=removed)
    else:
        emit("skill was not installed for the selected tool(s)", paths=[])
