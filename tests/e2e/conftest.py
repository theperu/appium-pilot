"""E2E harness: a black-box CLI runner + platform-parametrized session fixtures.

The CLI is driven as a subprocess (`python -m appium_pilot ...`) so tests exercise
the real arg parsing, output and exit codes. Sessions use the CLI's own auto-boot.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

from apps import get_app

CLI = [sys.executable, "-m", "appium_pilot"]


class Cli:
    def __init__(self, session: str, output_dir):
        self.session = session
        self.output_dir = str(output_dir)

    def run(self, *args, check=True, json_out=False, timeout=180):
        cmd = CLI + (["--json"] if json_out else []) + [f"-s={self.session}", *map(str, args)]
        env = {**os.environ, "APPIUM_PILOT_OUTPUT": self.output_dir}
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        if check and proc.returncode != 0:
            raise AssertionError(f"`{' '.join(map(str, args))}` rc={proc.returncode}\n{proc.stderr}")
        if json_out:
            return proc.returncode, json.loads(proc.stdout or proc.stderr or "{}")
        return proc.returncode, proc.stdout, proc.stderr

    def snapshot(self) -> str:
        return self.run("snapshot")[1]

    def ref_for(self, pattern: str):
        for line in self.snapshot().splitlines():
            if re.search(pattern, line):
                m = re.search(r'ref="(e\d+)"', line)
                if m:
                    return m.group(1)
        return None


@pytest.fixture(scope="session")
def app(platform):
    return get_app(platform)


@pytest.fixture(scope="session")
def session(platform, app, tmp_path_factory):
    """Open one app session per platform (auto-boots a device), reused across tests."""
    out = tmp_path_factory.mktemp(f"out-{platform}")
    cli = Cli(session=f"test-{platform}", output_dir=out)
    artifact = app.artifact()  # may pytest.skip if unavailable
    rc, _, err = cli.run(*app.open_args(artifact), check=False, timeout=420)
    if rc != 0:
        pytest.skip(f"could not open {platform} session (no device/toolchain?): {err.strip()[:300]}")
    yield cli
    # Exercises close-all + kill-all in teardown; next platform re-boots/re-starts.
    cli.run("close-all", check=False)
    cli.run("kill-all", check=False)


@pytest.fixture
def fresh(session, app):
    """Reset the app to its root screen before each test (terminate+activate)."""
    session.run("reset", check=False)
    session.run("wait", "--text", app.ready_text, "--timeout", "10", check=False)
    return session
