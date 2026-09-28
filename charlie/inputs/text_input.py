"""Terminal text input loop for Charlie.

Implements a clean, minimalist black-and-white interactive command loop.
"""

from __future__ import annotations

import os
from charlie.brain import parse
from charlie.output.speaker import output_response, print_banner, print_help
from charlie.router import dispatch


def run_text_loop() -> None:
    """Run interactive text-mode command loop in the terminal."""
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

        # Parse command into Action
        action = parse(raw)

        # Dispatch action to handler
        success, message = dispatch(action)

        # Display result and speak confirmation
        output_response(message, action_name=action.action if success else None)
