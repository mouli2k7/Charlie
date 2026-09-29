"""Terminal printing and speech synthesis output for Charlie.

Implements clean, minimalist black-and-white formatting and macOS `say` output.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Optional
from charlie.config import get_config


def list_available_voices() -> list[str]:
    """Return list of installed macOS voices."""
    if not shutil.which("say"):
        return []
    try:
        proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=False)
        voices = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts:
                voice_name = parts[0]
                if voice_name not in voices:
                    voices.append(voice_name)
        return voices
    except Exception:
        return []


def speak(
    text: str,
    non_blocking: bool = True,
    voice: Optional[str] = None,
) -> None:
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
        voice_to_use = voice or cfg.voice_name
        cmd = ["say"]
        if voice_to_use:
            cmd.extend(["-v", voice_to_use])
        cmd.append(clean_text)

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
    speak_param: Optional[bool] = None,
    voice: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Print the assistant response in clean B&W style and speak confirmation."""
    if speak_param is not None:
        speak_it = speak_param
    elif "speak" in kwargs:
        speak_it = kwargs["speak"]

    if action_name and action_name not in ("unknown", "answer"):
        print(f"[{action_name}] {message}")
    else:
        print(f"Charlie: {message}")

    if speak_it:
        speak(message, voice=voice)
