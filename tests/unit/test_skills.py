"""skills install/uninstall across the supported agent tools."""

import argparse

from appium_pilot.commands import skills_cmd


def _args(tmp_path, tool):
    return argparse.Namespace(dir=str(tmp_path), tool=tool, session="default")


def test_claude_install_uninstall(tmp_path):
    args = _args(tmp_path, "claude")
    skills_cmd.run_install(args)
    dest = tmp_path / "appium-pilot" / "SKILL.md"
    assert dest.exists() and "appium-pilot" in dest.read_text()
    skills_cmd.run_uninstall(args)
    assert not (tmp_path / "appium-pilot").exists()


def test_install_all_tools(tmp_path):
    skills_cmd.run_install(_args(tmp_path, "all"))
    assert (tmp_path / "appium-pilot" / "SKILL.md").exists()
    assert (tmp_path / ".cursor" / "rules" / "appium-pilot.mdc").exists()
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_agents_block_preserves_existing_content(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# My project\n\nexisting rules\n")
    args = _args(tmp_path, "agents")

    skills_cmd.run_install(args)
    text = agents.read_text()
    assert "existing rules" in text and "appium-pilot" in text  # appended, not clobbered

    skills_cmd.run_uninstall(args)
    text = agents.read_text()
    assert "existing rules" in text and "appium-pilot" not in text  # only our block removed
