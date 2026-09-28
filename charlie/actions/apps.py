"""App management action handlers for Charlie.

Scans installed macOS apps, resolves fuzzy names/aliases, and opens or closes them.
"""

from __future__ import annotations

import difflib
import os
import subprocess
from typing import Dict, List, Optional

# Standard macOS app search directories
APP_DIRECTORIES = [
    "/Applications",
    "/System/Applications",
    "/System/Applications/Utilities",
    os.path.expanduser("~/Applications"),
]

# Common aliases mapping user phrase -> official macOS app name
APP_ALIASES: Dict[str, str] = {
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "safari": "Safari",
    "spotify": "Spotify",
    "notes": "Notes",
    "terminal": "Terminal",
    "iterm": "iTerm",
    "iterm2": "iTerm2",
    "finder": "Finder",
    "messages": "Messages",
    "imessage": "Messages",
    "whatsapp": "WhatsApp",
    "mail": "Mail",
    "calendar": "Calendar",
    "calculator": "Calculator",
    "photos": "Photos",
    "music": "Music",
    "apple music": "Music",
    "reminders": "Reminders",
    "settings": "System Settings",
    "system settings": "System Settings",
    "system preferences": "System Settings",
    "slack": "Slack",
    "discord": "Discord",
    "telegram": "Telegram",
    "xcode": "Xcode",
    "keynote": "Keynote",
    "pages": "Pages",
    "numbers": "Numbers",
    "photoshop": "Adobe Photoshop",
}


class AppIndex:
    """Index of installed macOS applications."""

    def __init__(self) -> None:
        self._apps: Dict[str, str] = {}  # lowercase_name -> original_name
        self.refresh()

    def refresh(self) -> None:
        """Scan Application folders and index app names."""
        discovered: Dict[str, str] = {}
        for directory in APP_DIRECTORIES:
            if not os.path.isdir(directory):
                continue
            for root, subdirs, _ in os.walk(directory):
                # Avoid deep search into app bundles
                for sd in list(subdirs):
                    if sd.endswith(".app"):
                        app_name = sd[:-4]
                        discovered[app_name.lower()] = app_name
                        subdirs.remove(sd)
        self._apps = discovered

    @property
    def apps(self) -> Dict[str, str]:
        return self._apps

    def resolve(self, query: str) -> Optional[str]:
        """Resolve a query string to an installed app name.

        Matching priority:
        1. Exact match in index (case-insensitive)
        2. Alias table lookup
        3. Normalized match (without spaces/dashes)
        4. Fuzzy match using difflib (cutoff 0.6)
        """
        if not query or not query.strip():
            return None

        clean_query = query.strip()
        lower_query = clean_query.lower()

        # 1. Exact case-insensitive match
        if lower_query in self._apps:
            return self._apps[lower_query]

        # 2. Alias table check
        if lower_query in APP_ALIASES:
            alias_target = APP_ALIASES[lower_query]
            if alias_target.lower() in self._apps:
                return self._apps[alias_target.lower()]
            return alias_target

        # 3. Normalized string match (strip spaces and dashes)
        normalized_query = "".join(c for c in lower_query if c.isalnum())
        for l_name, original in self._apps.items():
            norm_name = "".join(c for c in l_name if c.isalnum())
            if norm_name == normalized_query:
                return original

        # 4. Fuzzy match
        matches = difflib.get_close_matches(lower_query, list(self._apps.keys()), n=1, cutoff=0.6)
        if matches:
            return self._apps[matches[0]]

        # If alias matched but app isn't explicitly indexed (e.g. system utility)
        for alias_key, alias_val in APP_ALIASES.items():
            if alias_key in lower_query or lower_query in alias_key:
                return alias_val

        return None


# Global singleton index
_app_index: Optional[AppIndex] = None


def get_app_index() -> AppIndex:
    """Return the cached AppIndex instance."""
    global _app_index
    if _app_index is None:
        _app_index = AppIndex()
    return _app_index


def open_app(app: str) -> tuple[bool, str]:
    """Open an installed macOS application safely without shell=True."""
    index = get_app_index()
    resolved = index.resolve(app)

    target_name = resolved or app.strip()
    try:
        # Use open -a with strict list arguments
        res = subprocess.run(
            ["open", "-a", target_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Opened {target_name}."

        if not resolved:
            return False, f"I couldn't find an app called {app}."
        return False, f"Could not open {target_name}: {res.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return False, f"Failed to open {target_name}: {str(e)}"


def close_app(app: str) -> tuple[bool, str]:
    """Gracefully quit a macOS application via osascript."""
    index = get_app_index()
    resolved = index.resolve(app)
    target_name = resolved or app.strip()

    # Escape double quotes for AppleScript safety
    safe_name = target_name.replace('"', '\\"')
    script = f'tell application "{safe_name}" to quit'

    try:
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Closed {target_name}."

        # If quit failed and app was unresolved, report not found
        if not resolved:
            return False, f"I couldn't find an app called {app}."
        return False, f"Could not close {target_name}: {res.stderr.strip() or 'App might not be running.'}"
    except Exception as e:
        return False, f"Failed to close {target_name}: {str(e)}"
