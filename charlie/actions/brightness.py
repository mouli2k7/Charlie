"""Brightness management action handlers for Charlie.

Controls macOS display brightness using native macOS DisplayServices framework,
with fallbacks to AppleScript System Events key codes and the brightness CLI.
"""

from __future__ import annotations

import ctypes
import re
import shutil
import subprocess
from typing import Optional

# macOS standard brightness key codes in System Events
KEY_CODE_BRIGHTNESS_UP = 144
KEY_CODE_BRIGHTNESS_DOWN = 145

_cached_brightness_level: int = 50

# Path to macOS native DisplayServices private framework
DISPLAY_SERVICES_PATH = (
    "/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices"
)


def _get_display_services() -> Optional[ctypes.CDLL]:
    """Load native macOS DisplayServices framework if available."""
    try:
        return ctypes.CDLL(DISPLAY_SERVICES_PATH)
    except Exception:
        return None


def read_brightness_displayservices() -> Optional[int]:
    """Read display brightness percentage using macOS DisplayServices."""
    ds = _get_display_services()
    if not ds:
        return None

    try:
        import Quartz

        main_display = Quartz.CGMainDisplayID()
        get_b = ds.DisplayServicesGetBrightness
        get_b.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
        get_b.restype = ctypes.c_int

        val = ctypes.c_float()
        res = get_b(main_display, ctypes.byref(val))
        if res == 0:
            return round(val.value * 100)
    except Exception:
        pass
    return None


def set_brightness_displayservices(level_pct: int) -> bool:
    """Set physical display brightness percentage using macOS DisplayServices."""
    ds = _get_display_services()
    if not ds:
        return False

    try:
        import Quartz

        main_display = Quartz.CGMainDisplayID()
        set_b = ds.DisplayServicesSetBrightness
        set_b.argtypes = [ctypes.c_uint32, ctypes.c_float]
        set_b.restype = ctypes.c_int

        float_val = max(0.0, min(1.0, level_pct / 100.0))
        res = set_b(main_display, ctypes.c_float(float_val))
        return res == 0
    except Exception:
        return False


def read_brightness_cli() -> Optional[int]:
    """Attempt to read brightness via brightness CLI (returns 0-100)."""
    if not shutil.which("brightness"):
        return None
    try:
        res = subprocess.run(
            ["brightness", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (res.stdout + res.stderr).lower()
        if res.returncode == 0 and "failed" not in output and "error" not in output:
            match = re.search(r"brightness\s+([0-9.]+)", res.stdout)
            if match:
                return round(float(match.group(1)) * 100)
    except Exception:
        pass
    return None


def set_brightness_cli(level_pct: int) -> bool:
    """Set brightness using the brightness CLI with strict error checking."""
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
        combined_output = (res.stdout + res.stderr).lower()
        # Ensure it didn't exit 0 while printing an internal display error
        if res.returncode == 0 and "failed" not in combined_output and "error" not in combined_output:
            return True
        return False
    except Exception:
        return False


def send_brightness_keys(key_code: int, times: int = 1) -> bool:
    """Send brightness key codes via AppleScript System Events."""
    if times <= 0:
        return True
    script = (
        f'tell application "System Events" to repeat {times} times\n'
        f"  key code {key_code}\n"
        f"  delay 0.02\n"
        f"end repeat"
    )
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


def get_current_brightness() -> int:
    """Read current display brightness percentage (defaults to cached level)."""
    global _cached_brightness_level
    val = read_brightness_displayservices()
    if val is not None:
        _cached_brightness_level = val
        return val

    val_cli = read_brightness_cli()
    if val_cli is not None:
        _cached_brightness_level = val_cli
        return val_cli

    return _cached_brightness_level


def brightness_set(level: int) -> tuple[bool, str]:
    """Set brightness to an exact percentage (0-100)."""
    global _cached_brightness_level
    clamped = max(0, min(100, int(level)))

    # 1. Native macOS DisplayServices (Hardware level, works on Apple Silicon & Intel)
    if set_brightness_displayservices(clamped):
        _cached_brightness_level = clamped
        return True, f"Brightness set to {clamped}%."

    # 2. Try brightness CLI (if working on connected external displays)
    if set_brightness_cli(clamped):
        _cached_brightness_level = clamped
        return True, f"Brightness set to {clamped}%."

    # 3. AppleScript key-code fallback (16 ticks = 100%)
    ticks = max(0, min(16, round(clamped / 6.25)))
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

    current_pct = get_current_brightness()
    target_pct = min(100, current_pct + step) if is_up else max(0, current_pct - step)

    # 1. Native macOS DisplayServices
    if set_brightness_displayservices(target_pct):
        _cached_brightness_level = target_pct
        return True, f"Brightness set to {target_pct}%."

    # 2. Try brightness CLI
    if set_brightness_cli(target_pct):
        _cached_brightness_level = target_pct
        return True, f"Brightness set to {target_pct}%."

    # 3. Key-code fallback
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
