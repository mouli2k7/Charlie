"""Tests for application resolution and matching."""

from unittest.mock import patch, MagicMock
from charlie.actions.apps import AppIndex, open_app, close_app


def test_app_index_resolve_exact():
    index = AppIndex()
    index._apps = {"safari": "Safari", "google chrome": "Google Chrome"}
    assert index.resolve("safari") == "Safari"
    assert index.resolve("Safari") == "Safari"


def test_app_index_resolve_aliases():
    index = AppIndex()
    index._apps = {"visual studio code": "Visual Studio Code"}
    assert index.resolve("vs code") == "Visual Studio Code"
    assert index.resolve("vscode") == "Visual Studio Code"
    assert index.resolve("code") == "Visual Studio Code"


def test_app_index_fuzzy_match():
    index = AppIndex()
    index._apps = {"spotify": "Spotify", "calculator": "Calculator"}
    assert index.resolve("spotifi") == "Spotify"
    assert index.resolve("calculater") == "Calculator"


@patch("subprocess.run")
def test_open_app_success(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stderr = ""

    with patch("charlie.actions.apps.get_app_index") as mock_get_index:
        mock_idx = MagicMock()
        mock_idx.resolve.return_value = "Safari"
        mock_get_index.return_value = mock_idx

        success, msg = open_app("safari")
        assert success is True
        assert "Opened Safari" in msg
        mock_run.assert_called_once_with(
            ["open", "-a", "Safari"],
            capture_output=True,
            text=True,
            check=False,
        )


@patch("subprocess.run")
def test_open_app_not_found(mock_run):
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Unable to find application"

    with patch("charlie.actions.apps.get_app_index") as mock_get_index:
        mock_idx = MagicMock()
        mock_idx.resolve.return_value = None
        mock_get_index.return_value = mock_idx

        success, msg = open_app("NonExistentApp123")
        assert success is False
        assert "couldn't find an app called NonExistentApp123" in msg
