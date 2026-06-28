"""Artifacts go to cwd; session state stays under home."""

from pathlib import Path

from appium_pilot import config


def test_output_dir_is_cwd_relative(tmp_path, monkeypatch):
    monkeypatch.delenv("APPIUM_PILOT_OUTPUT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert config.output_dir() == Path.cwd() / "appium-pilot"
    assert config.videos_dir() == Path.cwd() / "appium-pilot" / "videos"
    assert config.screenshots_dir() == Path.cwd() / "appium-pilot" / "screenshots"


def test_output_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("APPIUM_PILOT_OUTPUT", str(tmp_path / "evidence"))
    assert config.output_dir() == tmp_path / "evidence"
    assert config.videos_dir() == tmp_path / "evidence" / "videos"


def test_state_lives_under_home():
    assert ".appium-pilot" in str(config.SESSIONS_DIR)
