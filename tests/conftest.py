"""Top-level pytest config: register the --platform option early so it's known
before argument parsing (the E2E fixtures live in tests/e2e/conftest.py)."""


def pytest_addoption(parser):
    parser.addoption(
        "--platform", action="store", default="both",
        choices=["ios", "android", "both"], help="platform(s) for E2E tests",
    )


def pytest_generate_tests(metafunc):
    if "platform" in metafunc.fixturenames:
        sel = metafunc.config.getoption("--platform")
        plats = ["ios", "android"] if sel == "both" else [sel]
        metafunc.parametrize("platform", plats, scope="session")
