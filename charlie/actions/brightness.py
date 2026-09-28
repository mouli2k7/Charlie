"""Brightness management action handlers for Charlie.

Controls display brightness using the 'brightness' CLI with an AppleScript
key-code fallback via System Events.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Optional

# macOS standard brightness key codes in System Events
KEY_CODE_BRIGHTNESS_UP = 144
KEY_CODE_BRIGHTNESS_DOWN = 145

_cached_brightness_level: int = 50


def read_brightness_cli() -> Optional[float]:
    """Attempt to read brightness via brightness CLI (returns 0.0 - 1.0)."""
    if not shutil.which("brightness"):
        return None
    try:
        res = subprocess.run(
            ["brightness", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            match = re.search(r"brightness\s+([0-9.]+)", res.stdout)
            if match:
                return float(match.group(1))
    except Exception:
        pass
    return None


def set_brightness_cli(level_pct: int) -> bool:
    """Set brightness using the brightness CLI."""
    if not shutil.which("brightness"):
        return False
    val = max(0.0, min(1.0, level_pct / 100.0))
    try:
        res = subprocess.run(
            ["brightness", f"{val:.2f}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def send_brightness_keys(key_code: int, times: int = 1) -> bool:
    """Send brightness key codes via AppleScript System Events."""
    if times <= 0:
        return True
    script = f'tell application "System Events" to repeat {times} times\n  key code {key_code}\n  delay 0.02\nend repeat'
    try:
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def brightness_set(level: int) -> tuple[bool, str]:
    """Set brightness to an exact percentage (0-100)."""
    global _cached_brightness_level
    clamped = max(0, min(100, int(level)))

    # 1. Try brightness CLI
    if set_brightness_cli(clamped):
        _cached_brightness_level = clamped
        return True, f"Brightness set to {clamped}%."

    # 2. AppleScript key-code fallback (16 ticks = 100%)
    ticks = max(0, min(16, round(clamped / 6.25)))
    # Reset to 0 then step up
    reset_ok = send_brightness_keys(KEY_CODE_BRIGHTNESS_DOWN, 16)
    if reset_ok:
        send_brightness_keys(KEY_CODE_BRIGHTNESS_UP, ticks)
        _cached_brightness_level = clamped
        return True, f"Brightness set to ~{clamped}%."

    return (
        False,
        "Could not adjust brightness. Grant Accessibility permissions in "
        "System Settings -> Privacy & Security -> Accessibility.",
    )


def brightness_change(direction: str, amount: int = 10) -> tuple[bool, str]:
    """Increase or decrease brightness by a step percentage."""
    global _cached_brightness_level
    step = max(1, abs(int(amount)))
    is_up = direction.lower() == "up"

    # Try reading current brightness
    current_val = read_brightness_cli()
    if current_val is not None:
        current_pct = int(current_val * 100)
    else:
        current_pct = _cached_brightness_level

    target_pct = min(100, current_pct + step) if is_up else max(0, current_pct - step)

    # 1. Try brightness CLI
    if set_brightness_cli(target_pct):
        _cached_brightness_level = target_pct
        return True, f"Brightness set to {target_pct}%."

    # 2. Key-code fallback
    ticks = max(1, round(step / 6.25))
    key = KEY_CODE_BRIGHTNESS_UP if is_up else KEY_CODE_BRIGHTNESS_DOWN
    if send_brightness_keys(key, ticks):
        _cached_brightness_level = target_pct
        action_word = "increased" if is_up else "decreased"
        return True, f"Brightness {action_word}."

    return (
        False,
        "Could not adjust brightness. Grant Accessibility permissions in "
        "System Settings -> Privacy & Security -> Accessibility.",
    )
