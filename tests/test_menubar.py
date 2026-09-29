"""Unit tests for Charlie macOS Menu Bar App (Phase 4)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from charlie.schema import Action
from charlie.ui.menubar import CharlieMenuBarApp


class TestMenuBarApp(unittest.TestCase):
    """Test suite for CharlieMenuBarApp class."""

    @patch("charlie.ui.menubar.is_launch_at_login_enabled", return_value=False)
    @patch("charlie.ui.menubar.get_wake_word_listener")
    def setUp(self, mock_get_listener: MagicMock, _mock_login: MagicMock) -> None:
        mock_listener = MagicMock()
        mock_listener.is_running = False
        mock_get_listener.return_value = mock_listener

        self.app = CharlieMenuBarApp()

    def test_initial_menu_structure(self) -> None:
        self.assertEqual(self.app.title, "⚡ Charlie")
        self.assertIn("💬 Type a Command...", self.app.menu)
        self.assertIn("🎙️ Voice Command (Push-to-Talk)", self.app.menu)
        self.assertIn('⚡ Wake Word ("Hey Charlie")', self.app.menu)
        self.assertIn("🔊 Spoken Voice Responses", self.app.menu)
        self.assertIn("Last Result: Ready", self.app.menu)
        self.assertIn("🚀 Launch at Login", self.app.menu)
        self.assertIn("Quit Charlie", self.app.menu)

    def test_update_last_result(self) -> None:
        self.app._update_last_result("Short message")
        self.assertEqual(self.app.last_result_item.title, "Last: Short message")

        long_msg = "This is a very long message that should be truncated properly for the menu"
        self.app._update_last_result(long_msg)
        self.assertTrue(self.app.last_result_item.title.endswith("..."))
        self.assertLessEqual(len(self.app.last_result_item.title), 45)

    @patch("rumps.notification")
    def test_toggle_speech(self, mock_notif: MagicMock) -> None:
        initial = self.app._speech_enabled
        sender = MagicMock()

        self.app.on_toggle_speech(sender)
        self.assertEqual(self.app._speech_enabled, not initial)
        self.assertEqual(sender.state, 1 if not initial else 0)
        mock_notif.assert_called_once()

    @patch("rumps.notification")
    @patch("charlie.ui.menubar.toggle_launch_at_login")
    def test_toggle_launch_at_login(
        self,
        mock_toggle_login: MagicMock,
        mock_notif: MagicMock,
    ) -> None:
        mock_toggle_login.return_value = True
        sender = MagicMock()

        self.app.on_toggle_launch_at_login(sender)
        self.assertEqual(sender.state, 1)
        mock_notif.assert_called_once()

    @patch("charlie.ui.menubar.stop_wake_word_listener")
    @patch("charlie.ui.menubar.start_wake_word_listener")
    @patch("charlie.ui.menubar.get_wake_word_listener")
    @patch("rumps.notification")
    def test_toggle_wake_word(
        self,
        mock_notif: MagicMock,
        mock_get_listener: MagicMock,
        mock_start_listener: MagicMock,
        mock_stop_listener: MagicMock,
    ) -> None:
        mock_listener = MagicMock()
        mock_listener.is_running = False
        mock_get_listener.return_value = mock_listener

        sender = MagicMock()

        # Listener not running -> starts it
        self.app.on_toggle_wake_word(sender)
        mock_start_listener.assert_called_once()
        self.assertEqual(sender.state, 1)

        # Listener is running -> stops it
        mock_listener.is_running = True
        self.app.on_toggle_wake_word(sender)
        mock_stop_listener.assert_called_once()
        self.assertEqual(sender.state, 0)

    @patch("charlie.ui.menubar.parse")
    @patch("charlie.ui.menubar.dispatch")
    @patch("charlie.ui.menubar.output_response")
    @patch("rumps.notification")
    def test_process_command_worker_success(
        self,
        mock_notif: MagicMock,
        mock_out: MagicMock,
        mock_dispatch: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        mock_parse.return_value = Action(action="volume_set", params={"level": 50}, confidence=1.0)
        mock_dispatch.return_value = (True, "Set volume to 50%.")

        self.app._process_command_worker("set volume to 50")

        mock_parse.assert_called_once_with("set volume to 50")
        mock_dispatch.assert_called_once()
        mock_notif.assert_called_once()
        self.assertEqual(self.app.title, "⚡ Charlie")
        self.assertIn("50%", self.app.last_result_item.title)

    @patch("rumps.quit_application")
    @patch("charlie.ui.menubar.stop_wake_word_listener")
    def test_on_quit(
        self,
        mock_stop_listener: MagicMock,
        mock_quit: MagicMock,
    ) -> None:
        self.app.on_quit()
        mock_stop_listener.assert_called_once()
        mock_quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
