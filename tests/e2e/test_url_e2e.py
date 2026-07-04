"""E2E: deep-link `url` command.

Neither sample app registers a custom URL scheme, so a real deep-link landing
can't be asserted deterministically. This guards the weaker-but-real contract:
the command dispatches to the platform strategy and either succeeds or fails as
a clean one-line error — never a crash/traceback. (Scheme routing itself is
covered by unit tests + manual on-device checks.)
"""

import pytest

pytestmark = pytest.mark.e2e


def test_url_dispatches_cleanly(fresh):
    rc, out, err = fresh.run("url", "https://example.com", check=False)
    assert "Traceback" not in err
    if rc != 0:
        assert err.strip().startswith("error:")
