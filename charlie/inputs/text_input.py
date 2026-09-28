"""Terminal text + voice input loop for Charlie.

Phase 1: interactive text command loop.
Phase 2: adds 'v' or 'voice' to trigger push-to-talk voice listening.
Both modes feed the exact same command pipeline.
"""

from __future__ import annotations

import os
from charlie.brain import parse
from charlie.output.speaker import output_response, print_banner, print_help
from charlie.router import dispatch


def run_text_loop() -> None:
    """Run the interactive terminal command loop (text + optional voice)."""
    print_banner()

    while True:
        try:
            raw = input("charlie > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        cmd_lower = raw.lower()

        if cmd_lower in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        if cmd_lower in ("help", "?"):
            print_help()
            continue

        if cmd_lower in ("clear", "cls"):
            os.system("clear")
            print_banner()
            continue

        # Phase 2: Push-to-talk voice input trigger
        if cmd_lower in ("v", "voice", "listen", "talk"):
            _handle_voice_input()
            continue

        # Text command pipeline
        action = parse(raw)
        success, message = dispatch(action)
        output_response(message, action_name=action.action if success else None)


def _handle_voice_input() -> None:
    """Activate push-to-talk voice input and pipe through the command pipeline."""
    try:
        from charlie.inputs.voice_input import listen_and_transcribe
    except ImportError:
        print("Voice input not available: speech_recognition library missing.")
        return

    text = listen_and_transcribe()

    if not text or not text.strip():
        print("Charlie: No command detected.")
        return

    # Feed the transcription through the exact same pipeline as typed text
    action = parse(text)
    success, message = dispatch(action)
    output_response(message, action_name=action.action if success else None)
