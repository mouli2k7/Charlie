"""Tests for volume action handlers."""

from unittest.mock import patch, MagicMock
from charlie.actions.volume import (
    volume_set,
    volume_change,
    mute,
    unmute,
    get_current_volume,
)


@patch("subprocess.run")
def test_volume_set(mock_run):
    mock_run.return_value.returncode = 0
    success, msg = volume_set(40)
    assert success is True
    assert "40%" in msg
    mock_run.assert_called_once_with(
        ["osascript", "-e", "set volume output volume 40 without output muted"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("charlie.actions.volume.get_current_volume")
@patch("charlie.actions.volume.volume_set")
def test_volume_change_up(mock_set, mock_get):
    mock_get.return_value = 50
    mock_set.return_value = (True, "Volume set to 60%.")
    success, msg = volume_change("up", 10)
    assert success is True
    mock_set.assert_called_once_with(60)


@patch("charlie.actions.volume.get_current_volume")
@patch("charlie.actions.volume.volume_set")
def test_volume_change_down(mock_set, mock_get):
    mock_get.return_value = 50
    mock_set.return_value = (True, "Volume set to 40%.")
    success, msg = volume_change("down", 10)
    assert success is True
    mock_set.assert_called_once_with(40)


@patch("subprocess.run")
@patch("charlie.actions.volume.get_current_volume")
def test_mute_and_unmute(mock_get, mock_run):
    mock_get.return_value = 65
    mock_run.return_value.returncode = 0

    # Mute
    s_mute, msg_mute = mute()
    assert s_mute is True
    assert "muted" in msg_mute.lower()

    # Unmute restores previous level (65)
    s_unmute, msg_unmute = unmute()
    assert s_unmute is True
    assert "65%" in msg_unmute
