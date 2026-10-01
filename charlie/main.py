"""Charlie — Personal Voice + Text Assistant for macOS.

Main entry point.
"""

from __future__ import annotations

import argparse
import sys
import time
from charlie import __version__
from charlie.brain import parse
from charlie.inputs.text_input import run_text_loop
from charlie.output.speaker import output_response
from charlie.router import dispatch


def main() -> None:
    """CLI entry point for Charlie assistant."""
    parser = argparse.ArgumentParser(
        description="Charlie — Voice + Text Assistant for macOS",
    )
    parser.add_argument(
        "--command",
        "-c",
        type=str,
        help="Run a single text command and exit (one-shot mode).",
    )
    parser.add_argument(
        "--voice",
        "-V",
        action="store_true",
        help="Listen once via microphone, run the command, then exit (one-shot voice mode).",
    )
    parser.add_argument(
        "--wake-word",
        "-w",
        action="store_true",
        help="Run continuous 'Hey Charlie' wake word listener in background.",
    )
    parser.add_argument(
        "--app",
        "-a",
        action="store_true",
        help="Launch Charlie as a native macOS desktop app with menu bar integration.",
    )
    parser.add_argument(
        "--menubar",
        "-m",
        action="store_true",
        help="Launch Charlie as a menu-bar-only daemon.",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available macOS voices and exit.",
    )
    parser.add_argument(
        "--set-voice",
        type=str,
        metavar="VOICE",
        help="Set the active voice for Charlie (e.g. Samantha, Daniel, Karen, Rishi, Tara).",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"Charlie {__version__}",
    )

    args = parser.parse_args()

    # List voices
    if args.list_voices:
        from charlie.config import get_config
        from charlie.output.speaker import list_available_voices

        cfg = get_config()
        voices = list_available_voices()
        print(f"Current Voice: {cfg.voice_name}")
        print("\nRecommended English Voices:")
        print("  • Samantha (US Female, Siri-like)")
        print("  • Daniel   (UK Male, Jarvis-like)")
        print("  • Karen    (Australian Female)")
        print("  • Rishi    (Indian English Male)")
        print("  • Tara     (Indian English Female)")
        print("  • Alex     (Classic macOS Male)")
        print(f"\nAll Installed Voices ({len(voices)} available):")
        print("  " + ", ".join(voices[:35]) + ("..." if len(voices) > 35 else ""))
        sys.exit(0)

    # Set voice
    if args.set_voice:
        from charlie.config import save_setting
        from charlie.output.speaker import speak

        voice = args.set_voice.strip()
        save_setting("voice_name", voice)
        print(f"Charlie voice set to: {voice}")
        speak(f"Hello, my voice is now set to {voice}.", voice=voice)
        sys.exit(0)

    # Desktop GUI app mode (Phase 4)
    if args.app:
        from charlie.ui.app import run_charlie_app

        run_charlie_app()
        sys.exit(0)

    # Menu bar daemon mode
    if args.menubar:
        from charlie.ui.menubar import run_menubar_app

        run_menubar_app()
        sys.exit(0)

    # One-shot text mode
    if args.command:
        action = parse(args.command)
        success, message = dispatch(action)
        output_response(message, action_name=action.action if success else None)
        sys.exit(0 if success else 1)

    # One-shot voice mode
    if args.voice:
        from charlie.inputs.voice_input import listen_and_transcribe

        text = listen_and_transcribe()
        if not text:
            print("Charlie: No command detected.")
            sys.exit(1)
        action = parse(text)
        success, message = dispatch(action)
        output_response(message, action_name=action.action if success else None)
        sys.exit(0 if success else 1)

    # Dedicated background wake-word mode
    if args.wake_word:
        from charlie.inputs.wake_word import start_wake_word_listener, stop_wake_word_listener

        print(f"Starting Charlie Wake Word daemon (Charlie v{__version__})...")
        print("Say 'Hey Charlie' or 'Hey Charlie <command>' (Ctrl+C to quit).")
        listener = start_wake_word_listener()
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("\nStopping wake word listener...")
            stop_wake_word_listener()
            print("Goodbye!")
            sys.exit(0)

    # Interactive terminal loop (text + voice + wake word)
    run_text_loop()


if __name__ == "__main__":
    main()
