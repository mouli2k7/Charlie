"""Tests for wake word detection (Phase 3)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from charlie.inputs.wake_word import (
    WakeWordListener,
    build_wake_pattern,
    extract_wake_command,
)


class TestWakeWordPattern(unittest.TestCase):
    """Test wake word detection and command extraction logic."""

    def test_extract_wake_command_hey_charlie(self) -> None:
        triggered, cmd = extract_wake_command("hey charlie open safari")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "open safari")

    def test_extract_wake_command_with_punctuation(self) -> None:
        triggered, cmd = extract_wake_command("Charlie, set volume to 50")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "set volume to 50")

    def test_extract_wake_command_ok_charlie(self) -> None:
        triggered, cmd = extract_wake_command("ok charlie turn brightness down")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "turn brightness down")

    def test_extract_wake_command_colon_separator(self) -> None:
        triggered, cmd = extract_wake_command("Hey Charlie: pause music")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "pause music")

    def test_extract_wake_word_only(self) -> None:
        triggered, cmd = extract_wake_command("Hey Charlie")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "")

    def test_extract_wake_word_case_insensitive(self) -> None:
        triggered, cmd = extract_wake_command("HEY CHARLIE OPEN SPOTIFY")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "OPEN SPOTIFY")

    def test_extract_wake_word_not_triggered(self) -> None:
        triggered, cmd = extract_wake_command("open safari directly")
        self.assertFalse(triggered)
        self.assertEqual(cmd, "")

    def test_extract_wake_word_embedded_word_not_triggered(self) -> None:
        triggered, cmd = extract_wake_command("I like charlie chaplin movies")
        self.assertFalse(triggered)
        self.assertEqual(cmd, "")

    def test_custom_wake_word(self) -> None:
        triggered, cmd = extract_wake_command("computer launch terminal", wake_word="computer")
        self.assertTrue(triggered)
        self.assertEqual(cmd, "launch terminal")


class TestWakeWordListenerLifecycle(unittest.TestCase):
    """Test WakeWordListener start, stop, and dispatch behavior with mocks."""

    def test_listener_init(self) -> None:
        listener = WakeWordListener(wake_word="hey charlie")
        self.assertEqual(listener.wake_word, "hey charlie")
        self.assertFalse(listener.is_running)

    def test_listener_start_and_stop(self) -> None:
        listener = WakeWordListener()
        with patch.object(listener, "_listen_loop"):
            listener.start()
            self.assertTrue(listener.is_running)
            listener.stop()
            self.assertFalse(listener.is_running)

    def test_default_on_command_dispatches(self) -> None:
        listener = WakeWordListener()
        with patch("charlie.inputs.wake_word.parse") as mock_parse, \
             patch("charlie.inputs.wake_word.dispatch") as mock_dispatch, \
             patch("charlie.inputs.wake_word.output_response") as mock_output:
            mock_dispatch.return_value = (True, "Opened Spotify.")
            listener._default_on_command("open spotify")
            mock_parse.assert_called_once_with("open spotify")
            mock_dispatch.assert_called_once()
            mock_output.assert_called_once()


if __name__ == "__main__":
    unittest.main()
