"""Tests for the action router and handler dispatching."""

from unittest.mock import patch
from charlie.router import dispatch
from charlie.schema import Action


@patch("charlie.actions.apps.open_app")
def test_dispatch_open_app(mock_open):
    mock_open.return_value = (True, "Opened Safari.")
    action = Action(action="open_app", params={"app": "Safari"})
    success, msg = dispatch(action)
    assert success is True
    assert "Opened Safari" in msg
    mock_open.assert_called_once_with("Safari")


@patch("charlie.actions.apps.close_app")
def test_dispatch_close_app(mock_close):
    mock_close.return_value = (True, "Closed Chrome.")
    action = Action(action="close_app", params={"app": "Chrome"})
    success, msg = dispatch(action)
    assert success is True
    mock_close.assert_called_once_with("Chrome")


def test_dispatch_answer():
    action = Action(action="answer", params={"text": "It is 12:00 PM."})
    success, msg = dispatch(action)
    assert success is True
    assert msg == "It is 12:00 PM."


@patch("charlie.actions.web.web_search")
def test_dispatch_web_search(mock_search):
    mock_search.return_value = (True, "Searching Amazon.")
    action = Action(
        action="web_search",
        params={"site": "amazon", "query": "wireless earbuds", "browser": None},
    )
    success, msg = dispatch(action)
    assert success is True
    mock_search.assert_called_once_with(
        query="wireless earbuds",
        site="amazon",
        browser=None,
    )


@patch("charlie.actions.web.open_url")
def test_dispatch_open_url(mock_open_url):
    mock_open_url.return_value = (True, "Opening GitHub.")
    action = Action(
        action="open_url",
        params={"url": "https://github.com", "site": None, "browser": None},
    )
    success, msg = dispatch(action)
    assert success is True
    mock_open_url.assert_called_once_with(
        url="https://github.com",
        site=None,
        browser=None,
    )


@patch("charlie.actions.volume.volume_change")
def test_dispatch_volume_change(mock_vol):
    mock_vol.return_value = (True, "Volume set to 60%.")
    action = Action(action="volume_change", params={"direction": "up", "amount": 10})
    success, msg = dispatch(action)
    assert success is True
    mock_vol.assert_called_once_with(direction="up", amount=10)


@patch("charlie.actions.volume.volume_set")
def test_dispatch_volume_set(mock_vol):
    mock_vol.return_value = (True, "Volume set to 40%.")
    action = Action(action="volume_set", params={"level": 40})
    success, msg = dispatch(action)
    assert success is True
    mock_vol.assert_called_once_with(level=40)


@patch("charlie.actions.volume.mute")
def test_dispatch_mute(mock_mute):
    mock_mute.return_value = (True, "Audio muted.")
    action = Action(action="mute", params={})
    success, msg = dispatch(action)
    assert success is True
    mock_mute.assert_called_once()


@patch("charlie.actions.volume.unmute")
def test_dispatch_unmute(mock_unmute):
    mock_unmute.return_value = (True, "Audio unmuted to 50%.")
    action = Action(action="unmute", params={})
    success, msg = dispatch(action)
    assert success is True
    mock_unmute.assert_called_once()


@patch("charlie.actions.brightness.brightness_change")
def test_dispatch_brightness_change(mock_b):
    mock_b.return_value = (True, "Brightness increased.")
    action = Action(action="brightness_change", params={"direction": "up", "amount": 10})
    success, msg = dispatch(action)
    assert success is True
    mock_b.assert_called_once_with(direction="up", amount=10)


@patch("charlie.actions.brightness.brightness_set")
def test_dispatch_brightness_set(mock_b):
    mock_b.return_value = (True, "Brightness set to 50%.")
    action = Action(action="brightness_set", params={"level": 50})
    success, msg = dispatch(action)
    assert success is True
    mock_b.assert_called_once_with(level=50)


@patch("charlie.actions.media.media_control")
def test_dispatch_media_control(mock_media):
    mock_media.return_value = (True, "Play/Pause toggled.")
    action = Action(action="media_control", params={"command": "play_pause"})
    success, msg = dispatch(action)
    assert success is True
    mock_media.assert_called_once_with(command="play_pause")


def test_dispatch_unknown():
    action = Action(action="unknown", params={"reason": "Unrecognized"})
    success, msg = dispatch(action)
    assert success is False
    assert msg == "Unrecognized"
