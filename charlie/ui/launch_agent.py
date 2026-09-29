"""LaunchAgent plist manager for Charlie auto-start at macOS login (Phase 4)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import plistlib
import sys
from typing import Optional

logger = logging.getLogger(__name__)

PLIST_NAME = "com.charlie.assistant.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / PLIST_NAME


def is_launch_at_login_enabled() -> bool:
    """Check if Charlie LaunchAgent plist exists in ~/Library/LaunchAgents."""
    return PLIST_PATH.is_file()


def enable_launch_at_login(
    python_bin: Optional[str] = None,
    work_dir: Optional[str] = None,
) -> bool:
    """Create ~/Library/LaunchAgents/com.charlie.assistant.plist to auto-start Charlie at login.

    Returns True on success, False on failure.
    """
    try:
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

        py_exec = python_bin or sys.executable
        cwd = work_dir or str(Path(__file__).resolve().parent.parent.parent)

        plist_data = {
            "Label": "com.charlie.assistant",
            "ProgramArguments": [
                py_exec,
                "-m",
                "charlie.main",
                "--app",
            ],
            "RunAtLoad": True,
            "KeepAlive": False,
            "WorkingDirectory": cwd,
            "StandardOutPath": "/tmp/charlie.out",
            "StandardErrorPath": "/tmp/charlie.err",
            "EnvironmentVariables": {
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"),
            },
        }

        with open(PLIST_PATH, "wb") as f:
            plistlib.dump(plist_data, f)

        logger.info("Created LaunchAgent plist at %s", PLIST_PATH)
        return True
    except Exception as e:
        logger.error("Failed to enable launch at login: %s", e)
        return False


def disable_launch_at_login() -> bool:
    """Remove Charlie LaunchAgent plist from ~/Library/LaunchAgents.

    Returns True on success, False on failure.
    """
    try:
        if PLIST_PATH.is_file():
            PLIST_PATH.unlink()
            logger.info("Removed LaunchAgent plist at %s", PLIST_PATH)
        return True
    except Exception as e:
        logger.error("Failed to disable launch at login: %s", e)
        return False


def toggle_launch_at_login() -> bool:
    """Toggle launch at login state. Returns the new state (True = enabled, False = disabled)."""
    if is_launch_at_login_enabled():
        disable_launch_at_login()
        return False
    else:
        enable_launch_at_login()
        return True
