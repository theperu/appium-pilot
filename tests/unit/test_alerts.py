"""System-alert handling (§2.1): strategy alert verbs + open's auto-accept cap.

The command layer is thin (Session.load → attach → strategy call), so the
device-free coverage lives on the strategy methods (driven by a fake W3C alert
channel) and the per-platform capability map.
"""

from selenium.common.exceptions import NoAlertPresentException

from appium_pilot.commands.open_cmd import AUTO_ACCEPT_ALERT_CAP
from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")


class _Alert:
    def __init__(self, text):
        self.text = text
        self.accepted = False
        self.dismissed = False

    def accept(self):
        self.accepted = True

    def dismiss(self):
        self.dismissed = True


class _SwitchTo:
    def __init__(self, alert):
        self._alert = alert

    @property
    def alert(self):
        if self._alert is None:
            raise NoAlertPresentException()
        return self._alert


class _Driver:
    def __init__(self, alert=None):
        self.switch_to = _SwitchTo(alert)


def test_alert_text_none_when_no_alert():
    assert AND.alert_text(_Driver(None)) is None
    assert IOS.alert_text(_Driver(None)) is None


def test_alert_text_returns_message():
    assert AND.alert_text(_Driver(_Alert("Allow notifications?"))) == "Allow notifications?"


def test_accept_alert_calls_through():
    alert = _Alert("Delete?")
    AND.accept_alert(_Driver(alert))
    assert alert.accepted and not alert.dismissed


def test_dismiss_alert_calls_through():
    alert = _Alert("Delete?")
    IOS.dismiss_alert(_Driver(alert))
    assert alert.dismissed and not alert.accepted


def test_auto_accept_cap_is_platform_specific():
    assert AUTO_ACCEPT_ALERT_CAP["android"] == {"appium:autoGrantPermissions": True}
    assert AUTO_ACCEPT_ALERT_CAP["ios"] == {"appium:autoAcceptAlerts": True}
