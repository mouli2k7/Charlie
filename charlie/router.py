"""Action router for Charlie.

Dispatches validated Action objects to their dedicated action handlers.
Enforces that only whitelisted actions are executed.
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple
from charlie.actions import apps, brightness, media, volume, web
from charlie.schema import Action

ActionHandler = Callable[..., Tuple[bool, str]]

HANDLER_MAP: Dict[str, ActionHandler] = {
    "open_app": lambda p: apps.open_app(p["app"]),
    "close_app": lambda p: apps.close_app(p["app"]),
    "web_search": lambda p: web.web_search(
        query=p["query"],
        site=p.get("site", "google"),
        browser=p.get("browser"),
    ),
    "open_url": lambda p: web.open_url(
        url=p.get("url"),
        site=p.get("site"),
        browser=p.get("browser"),
    ),
    "volume_change": lambda p: volume.volume_change(
        direction=p["direction"],
        amount=p.get("amount", 10),
    ),
    "volume_set": lambda p: volume.volume_set(level=p["level"]),
    "mute": lambda p: volume.mute(),
    "unmute": lambda p: volume.unmute(),
    "brightness_change": lambda p: brightness.brightness_change(
        direction=p["direction"],
        amount=p.get("amount", 10),
    ),
    "brightness_set": lambda p: brightness.brightness_set(level=p["level"]),
    "media_control": lambda p: media.media_control(command=p["command"]),
    "answer": lambda p: (True, p.get("text", "")),
}


def dispatch(action: Action) -> Tuple[bool, str]:
    """Execute the given action safely and return (success, message)."""
    if action.action == "unknown":
        reason = action.params.get("reason", "I didn't understand that command.")
        return False, reason

    handler = HANDLER_MAP.get(action.action)
    if not handler:
        return False, f"Action '{action.action}' is not supported."

    try:
        success, message = handler(action.params)
        return success, message
    except Exception as err:
        return False, f"Error running {action.action}: {str(err)}"
