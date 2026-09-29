"""Unit tests for Charlie launch agent plist manager (Phase 4)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from charlie.ui.launch_agent import (
    disable_launch_at_login,
    enable_launch_at_login,
    is_launch_at_login_enabled,
    toggle_launch_at_login,
)


class TestLaunchAgent(unittest.TestCase):
    """Test suite for LaunchAgent management."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_plist_path = Path(self.temp_dir.name) / "com.charlie.assistant.plist"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_enable_and_check_launch_agent(self) -> None:
        with patch("charlie.ui.launch_agent.PLIST_PATH", self.mock_plist_path), \
             patch("charlie.ui.launch_agent.LAUNCH_AGENTS_DIR", Path(self.temp_dir.name)):
            self.assertFalse(is_launch_at_login_enabled())

            success = enable_launch_at_login(
                python_bin="/usr/bin/python3",
                work_dir="/tmp/test",
            )
            self.assertTrue(success)
            self.assertTrue(is_launch_at_login_enabled())
            self.assertTrue(self.mock_plist_path.is_file())

            # Disable
            disable_success = disable_launch_at_login()
            self.assertTrue(disable_success)
            self.assertFalse(is_launch_at_login_enabled())

    def test_toggle_launch_agent(self) -> None:
        with patch("charlie.ui.launch_agent.PLIST_PATH", self.mock_plist_path), \
             patch("charlie.ui.launch_agent.LAUNCH_AGENTS_DIR", Path(self.temp_dir.name)):
            # Initially disabled -> toggle enables it
            state1 = toggle_launch_at_login()
            self.assertTrue(state1)
            self.assertTrue(is_launch_at_login_enabled())

            # Enabled -> toggle disables it
            state2 = toggle_launch_at_login()
            self.assertFalse(state2)
            self.assertFalse(is_launch_at_login_enabled())


if __name__ == "__main__":
    unittest.main()
