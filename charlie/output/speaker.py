"""Terminal printing and speech synthesis output for Charlie.

Implements clean, minimalist black-and-white formatting and macOS `say` output.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional
from charlie.config import get_config


def speak(text: str, non_blocking: bool = True) -> None:
    """Speak text using the macOS `say` command if enabled in configuration."""
    if not text or not text.strip():
        return

    cfg = get_config()
    if not cfg.speak_responses:
        return

    if not shutil.which("say"):
        return

    try:
        clean_text = text.strip()
        cmd = ["say", clean_text]
        if non_blocking:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    except Exception:
        pass


def print_banner() -> None:
    """Print a clean, minimal black-and-white startup banner."""
    cfg = get_config()
    llm_info = "Gemini LLM active" if cfg.gemini_api_key else ("Claude active" if cfg.anthropic_api_key else "Offline rules")

    print()
    print("┌──────────────────────────────────────────────┐")
    print("│  CHARLIE — macOS Personal Assistant          │")
    print(f"│  {llm_info:<44}│")
    print("│  Type a command  •  'v' for voice input      │")
    print("│  'w' for 'Hey Charlie' wake word listener    │")
    print("│  'help' for examples  •  'q' to quit          │")
    print("└──────────────────────────────────────────────┘")
    print()


def print_help() -> None:
    """Print clean help documentation showing example commands."""
    print()
    print("Available Commands & Examples:")
    print("  Apps:        open safari | launch notes | close chrome | quit spotify")
    print("  Web Search:  open amazon and search for wireless earbuds")
    print("               search running shoes on flipkart | google best laptops")
    print("  Open URL:    open youtube | go to github.com | can you pull up youtube for me")
    print("  Volume:      volume up | volume down | turn it down a bit | set volume to 40 | mute | unmute")
    print("  Brightness:  brightness up | make the screen dimmer | set brightness to 50")
    print("  Media:       play | pause | next song | previous track")
    print("  Voice:       v  (push-to-talk mic input)")
    print("  Wake Word:   w  (toggle background 'Hey Charlie' listener)")
    print("  System:      help | clear | exit | quit")
    print()


def output_response(
    message: str,
    action_name: Optional[str] = None,
    speak_it: bool = True,
) -> None:
    """Print the assistant response in clean B&W style and speak confirmation."""
    if action_name and action_name != "unknown":
        print(f"[{action_name}] {message}")
    else:
        print(f"Charlie: {message}")

    if speak_it:
        speak(message)
