"""Volume management action handlers for Charlie.

Controls macOS output volume and mute state via osascript.
"""

from __future__ import annotations

import subprocess

# In-memory storage for previous volume before muting
_pre_mute_volume: int = 50


def get_current_volume() -> int:
    """Read the current macOS output volume (0-100)."""
    try:
        res = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return int(res.stdout.strip())
    except Exception:
        pass
    return 50


def is_muted() -> bool:
    """Check if macOS output volume is currently muted."""
    try:
        res = subprocess.run(
            ["osascript", "-e", "output muted of (get volume settings)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip().lower() == "true"
    except Exception:
        pass
    return False


def volume_set(level: int) -> tuple[bool, str]:
    """Set the system output volume to an exact level between 0 and 100."""
    clamped = max(0, min(100, int(level)))
    try:
        # Also ensure unmuted if user sets a non-zero volume
        script = f"set volume output volume {clamped}"
        if clamped > 0:
            script += " without output muted"
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Volume set to {clamped}%."
        return False, f"Failed to set volume: {res.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return False, f"Failed to set volume: {str(e)}"


def volume_change(direction: str, amount: int = 10) -> tuple[bool, str]:
    """Increase or decrease volume by the specified step amount."""
    current = get_current_volume()
    step = max(1, abs(int(amount)))

    if direction.lower() == "up":
        target = min(100, current + step)
    else:
        target = max(0, current - step)

    return volume_set(target)


def mute() -> tuple[bool, str]:
    """Mute the system audio output while saving current level."""
    global _pre_mute_volume
    current = get_current_volume()
    if current > 0:
        _pre_mute_volume = current

    try:
        res = subprocess.run(
            ["osascript", "-e", "set volume with output muted"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, "Audio muted."
        return False, f"Failed to mute: {res.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return False, f"Failed to mute: {str(e)}"


def unmute() -> tuple[bool, str]:
    """Unmute the system audio output and restore previous level."""
    global _pre_mute_volume
    restore_level = _pre_mute_volume if _pre_mute_volume > 0 else 40

    try:
        res = subprocess.run(
            [
                "osascript",
                "-e",
                f"set volume without output muted output volume {restore_level}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Audio unmuted to {restore_level}%."
        return False, f"Failed to unmute: {res.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return False, f"Failed to unmute: {str(e)}"
