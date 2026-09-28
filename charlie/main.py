"""Charlie — Personal Voice + Text Assistant for macOS.

Main entry point.
"""

from __future__ import annotations

import argparse
import sys
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
        "--version",
        "-v",
        action="version",
        version=f"Charlie {__version__}",
    )

    args = parser.parse_args()

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

    # Interactive terminal loop (text + voice)
    run_text_loop()


if __name__ == "__main__":
    main()
