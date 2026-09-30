"""Media control action handlers for Charlie.

Posts system-defined NSEvents through Quartz to simulate hardware media keys
(play/pause, next track, previous track) for system-wide playback control.
"""

from __future__ import annotations

import subprocess
from typing import Literal

# macOS system-defined media key codes
NX_KEYTYPE_PLAY = 16
NX_KEYTYPE_NEXT = 17
NX_KEYTYPE_PREVIOUS = 18

MEDIA_KEY_MAP = {
    "play_pause": NX_KEYTYPE_PLAY,
    "next": NX_KEYTYPE_NEXT,
    "previous": NX_KEYTYPE_PREVIOUS,
}


def _post_quartz_key(key_code: int) -> bool:
    """Post key down and up events using Quartz system-defined events."""
    try:
        import Quartz

        for down in (True, False):
            flags = 0xA00 if down else 0xB00
            data1 = (key_code << 16) | flags
            ev = Quartz.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                14,  # NSSystemDefined
                Quartz.NSPoint(0, 0),
                flags,
                0,
                0,
                0,
                8,  # Media key subtype
                data1,
                -1,
            )
            if ev:
                cg_ev = ev.CGEvent()
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, cg_ev)
        return True
    except Exception:
        return False


def _applescript_media_fallback(command: str) -> bool:
    """Fallback to AppleScript for common media players (Spotify, Apple Music) if Quartz is restricted."""
    cmds = {
        "play_pause": [("Spotify", "playpause"), ("Music", "playpause")],
        "next": [("Spotify", "next track"), ("Music", "next track")],
        "previous": [("Spotify", "previous track"), ("Music", "previous track")],
    }
    targets = cmds.get(command)
    if not targets:
        return False

    for app_name, app_cmd in targets:
        try:
            res = subprocess.run(
                ["osascript", "-e", f'tell application "{app_name}" to {app_cmd}'],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass
    return False


def media_control(command: Literal["play_pause", "next", "previous"]) -> tuple[bool, str]:
    """Dispatch media playback commands."""
    key_code = MEDIA_KEY_MAP.get(command)
    if key_code is None:
        return False, f"Unknown media command: {command}"

    # 1. Preferred Quartz system-wide media key
    if _post_quartz_key(key_code):
        labels = {
            "play_pause": "Play/Pause toggled.",
            "next": "Skipped to next track.",
            "previous": "Returned to previous track.",
        }
        return True, labels.get(command, f"Media command '{command}' executed.")

    # 2. AppleScript fallback
    if _applescript_media_fallback(command):
        return True, f"Media command '{command}' executed via player fallback."

    return (
        False,
        "Could not send media key. Grant Accessibility permissions in "
        "System Settings -> Privacy & Security -> Accessibility.",
    )
