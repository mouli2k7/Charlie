"""Visual and audible wake word confirmation popups for Charlie (Phase 4).

Displays an on-screen dialog, native banner notification, and subtle chime
whenever 'Hey Charlie' is recognized by the microphone listener.
"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
from typing import Optional

from charlie.config import get_config

logger = logging.getLogger(__name__)

# Standard macOS system chime sound
_SYSTEM_CHIME_PATH = Path("/System/Library/Sounds/Tink.aiff")


def show_wake_popup(
    command: Optional[str] = None,
    style: Optional[str] = None,
    title: str = "Charlie",
) -> None:
    """Trigger visual popup and audio chime when wake word is recognized.

    Args:
        command: Optional command transcribed after wake word.
        style: 'both' (dialog + banner), 'dialog', 'banner', or 'none'.
               Defaults to configured `wake_popup_style`.
        title: Title for notification and alert window.
    """
    cfg = get_config()
    popup_style = (style or cfg.wake_popup_style or "both").lower()

    if popup_style == "none":
        return

    # 1. Non-blocking audio chime
    try:
        if _SYSTEM_CHIME_PATH.is_file():
            subprocess.Popen(
                ["afplay", str(_SYSTEM_CHIME_PATH)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        logger.debug("Chime playback error: %s", e)

    # Clean message text
    if command and command.strip():
        msg_text = f'Heard: "{command.strip()}"'
        dlg_text = f"⚡ Hey Charlie recognized!\n\nProcessing: \"{command.strip()}\""
    else:
        msg_text = "Listening for your command..."
        dlg_text = "⚡ Hey Charlie recognized!\n\nListening for your command..."

    # Escape backslashes and double quotes for AppleScript string literals
    safe_msg = msg_text.replace('\\', '\\\\').replace('"', '\\"')
    safe_dlg = dlg_text.replace('\\', '\\\\').replace('"', '\\"')

    # 2. Native macOS banner notification (top-right slide-in)
    if popup_style in ("both", "banner"):
        try:
            script = f'display notification "{safe_msg}" with title "{title}" subtitle "⚡ Voice Recognized"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("Failed to display notification banner: %s", e)

    # 3. Small on-screen alert dialog (auto-dismisses after 2 seconds)
    if popup_style in ("both", "dialog"):
        try:
            alert_script = f'display alert "{title}" message "{safe_dlg}" giving up after 2'
            subprocess.Popen(
                ["osascript", "-e", alert_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("Failed to display alert dialog: %s", e)
