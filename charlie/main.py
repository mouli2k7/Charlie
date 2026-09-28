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
        help="Run a single command and exit (one-shot mode).",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"Charlie {__version__}",
    )

    args = parser.parse_args()

    if args.command:
        action = parse(args.command)
        success, message = dispatch(action)
        output_response(message, action_name=action.action if success else None)
        sys.exit(0 if success else 1)

    # Interactive terminal loop
    run_text_loop()


if __name__ == "__main__":
    main()
