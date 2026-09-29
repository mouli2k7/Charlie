"""Unit tests for Charlie wake word popup module (Phase 4)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from charlie.ui.popup import show_wake_popup


class TestWakePopup(unittest.TestCase):
    """Test suite for wake popup triggers."""

    @patch("subprocess.Popen")
    def test_show_wake_popup_both(self, mock_popen: MagicMock) -> None:
        show_wake_popup(command="what is the time", style="both")
        self.assertGreaterEqual(mock_popen.call_count, 2)

    @patch("subprocess.Popen")
    def test_show_wake_popup_banner_only(self, mock_popen: MagicMock) -> None:
        show_wake_popup(command=None, style="banner")
        # Should call chime and notification
        self.assertGreaterEqual(mock_popen.call_count, 1)

    @patch("subprocess.Popen")
    def test_show_wake_popup_dialog_only(self, mock_popen: MagicMock) -> None:
        show_wake_popup(command="open terminal", style="dialog")
        self.assertGreaterEqual(mock_popen.call_count, 1)

    @patch("subprocess.Popen")
    def test_show_wake_popup_none(self, mock_popen: MagicMock) -> None:
        show_wake_popup(command="open terminal", style="none")
        mock_popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
