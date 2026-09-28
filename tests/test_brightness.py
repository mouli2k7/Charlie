"""Tests for display brightness action handlers."""

from unittest.mock import patch, MagicMock
from charlie.actions.brightness import (
    brightness_set,
    brightness_change,
    set_brightness_displayservices,
    read_brightness_displayservices,
)


@patch("charlie.actions.brightness.set_brightness_displayservices")
def test_brightness_set_via_displayservices(mock_set):
    mock_set.return_value = True
    success, msg = brightness_set(75)
    assert success is True
    assert "75%" in msg
    mock_set.assert_called_once_with(75)


@patch("charlie.actions.brightness.get_current_brightness")
@patch("charlie.actions.brightness.set_brightness_displayservices")
def test_brightness_change_up(mock_set, mock_get):
    mock_get.return_value = 50
    mock_set.return_value = True
    success, msg = brightness_change("up", 15)
    assert success is True
    assert "65%" in msg
    mock_set.assert_called_once_with(65)


@patch("charlie.actions.brightness.get_current_brightness")
@patch("charlie.actions.brightness.set_brightness_displayservices")
def test_brightness_change_down(mock_set, mock_get):
    mock_get.return_value = 50
    mock_set.return_value = True
    success, msg = brightness_change("down", 10)
    assert success is True
    assert "40%" in msg
    mock_set.assert_called_once_with(40)


@patch("charlie.actions.brightness.set_brightness_displayservices")
@patch("charlie.actions.brightness.set_brightness_cli")
@patch("charlie.actions.brightness.send_brightness_keys")
def test_brightness_fallback_to_keys(mock_keys, mock_cli, mock_ds):
    mock_ds.return_value = False
    mock_cli.return_value = False
    mock_keys.return_value = True

    success, msg = brightness_set(50)
    assert success is True
    assert "~50%" in msg
