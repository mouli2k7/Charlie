"""macOS Menu Bar interface for Charlie using rumps (Phase 4).

Provides a neat, modern, and lightweight menu-bar application for Charlie:
- Push-to-Talk voice recognition
- Interactive text command popup window
- Real-time notification banners
- Background 'Hey Charlie' wake word toggle
- Spoken voice feedback mute/unmute toggle
- Launch at login manager
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import rumps

from charlie import __version__
from charlie.brain import parse
from charlie.config import get_config
from charlie.inputs.wake_word import (
    get_wake_word_listener,
    start_wake_word_listener,
    stop_wake_word_listener,
)
from charlie.output.speaker import output_response
from charlie.router import dispatch
from charlie.ui.launch_agent import (
    is_launch_at_login_enabled,
    toggle_launch_at_login,
)

logger = logging.getLogger(__name__)


class CharlieMenuBarApp(rumps.App):
    """Native macOS menu-bar app for Charlie."""

    def __init__(self) -> None:
        super().__init__(
            name="Charlie",
            title="⚡ Charlie",
            quit_button=None,  # Custom quit handler to cleanly stop background threads
        )

        self.cfg = get_config()
        self.is_processing = False
        self._speech_enabled = self.cfg.speak_responses

        # Menu Items
        self.title_item = rumps.MenuItem(f"Charlie Assistant (v{__version__})")
        self.status_item = rumps.MenuItem("● Status: Ready")
        self.type_cmd_item = rumps.MenuItem(
            "💬 Type a Command...",
            callback=self.on_type_command,
            key="t",
        )
        self.talk_item = rumps.MenuItem(
            "🎙️ Voice Command (Push-to-Talk)",
            callback=self.on_voice_command,
            key="v",
        )
        self.wake_word_item = rumps.MenuItem(
            '⚡ Wake Word ("Hey Charlie")',
            callback=self.on_toggle_wake_word,
        )
        self.speech_item = rumps.MenuItem(
            "🔊 Spoken Voice Responses",
            callback=self.on_toggle_speech,
        )
        self.last_result_item = rumps.MenuItem("Last Result: Ready")
        self.login_item = rumps.MenuItem(
            "🚀 Launch at Login",
            callback=self.on_toggle_launch_at_login,
        )
        self.quit_item = rumps.MenuItem(
            "Quit Charlie",
            callback=self.on_quit,
            key="q",
        )

        # Initial checkmark states
        listener = get_wake_word_listener()
        self.wake_word_item.state = 1 if listener.is_running else 0
        self.speech_item.state = 1 if self._speech_enabled else 0
        self.login_item.state = 1 if is_launch_at_login_enabled() else 0

        # Assemble neat and modern menu
        self.menu = [
            self.title_item,
            self.status_item,
            rumps.separator,
            self.type_cmd_item,
            self.talk_item,
            rumps.separator,
            self.wake_word_item,
            self.speech_item,
            rumps.separator,
            self.last_result_item,
            self.login_item,
            rumps.separator,
            self.quit_item,
        ]

    def _update_last_result(self, message: str) -> None:
        """Update last result display in menu."""
        clean = message.replace("\n", " ").strip()
        if len(clean) > 35:
            self.last_result_item.title = f"Last: {clean[:32]}..."
        else:
            self.last_result_item.title = f"Last: {clean}"

    def on_type_command(self, _sender: Optional[rumps.MenuItem] = None) -> None:
        """Display interactive modal input dialog for text commands."""
        if self.is_processing:
            rumps.notification("Charlie", "", "Charlie is currently busy.")
            return

        window = rumps.Window(
            message=(
                "Ask a question or enter a command:\n"
                "(e.g., 'who is the CEO of Google', 'what's the temperature in Delhi', 'volume 50', 'open safari')"
            ),
            title="Charlie Assistant",
            default_text="",
            ok="Run",
            cancel="Cancel",
            dimensions=(360, 24),
        )
        response = window.run()
        if response.clicked and response.text.strip():
            command = response.text.strip()
            threading.Thread(
                target=self._process_command_worker,
                args=(command,),
                daemon=True,
                name="CharlieMenuBarTextWorker",
            ).start()

    def on_voice_command(self, _sender: Optional[rumps.MenuItem] = None) -> None:
        """Trigger push-to-talk voice recording and command execution."""
        if self.is_processing:
            rumps.notification("Charlie", "", "Charlie is currently busy.")
            return

        threading.Thread(
            target=self._process_voice_worker,
            daemon=True,
            name="CharlieMenuBarVoiceWorker",
        ).start()

    def on_toggle_wake_word(self, sender: rumps.MenuItem) -> None:
        """Toggle continuous background wake word listener."""
        listener = get_wake_word_listener()
        if listener.is_running:
            stop_wake_word_listener()
            sender.state = 0
            rumps.notification("Charlie", "Wake Word", "Background wake word listener paused.")
        else:
            start_wake_word_listener(on_command=self._on_wake_command_heard)
            sender.state = 1
            rumps.notification("Charlie", "Wake Word", "Listening in background for 'Hey Charlie'.")

    def on_toggle_speech(self, sender: rumps.MenuItem) -> None:
        """Toggle spoken voice feedback on or off."""
        self._speech_enabled = not self._speech_enabled
        self.cfg.speak_responses = self._speech_enabled
        sender.state = 1 if self._speech_enabled else 0
        status_msg = "Spoken responses enabled." if self._speech_enabled else "Spoken responses muted."
        rumps.notification("Charlie", "Voice Feedback", status_msg)

    def on_toggle_launch_at_login(self, sender: rumps.MenuItem) -> None:
        """Toggle LaunchAgent plist to launch Charlie automatically at login."""
        new_state = toggle_launch_at_login()
        sender.state = 1 if new_state else 0
        msg = "Charlie will launch automatically at login." if new_state else "Launch at login disabled."
        rumps.notification("Charlie", "Launch at Login", msg)

    def on_quit(self, _sender: Optional[rumps.MenuItem] = None) -> None:
        """Gracefully shut down background threads and quit."""
        try:
            stop_wake_word_listener()
        except Exception:
            pass
        rumps.quit_application()

    def _process_command_worker(self, command: str) -> None:
        """Process text command in background thread to keep Cocoa main loop responsive."""
        self.is_processing = True
        self.title = "⚡ Thinking..."
        self.status_item.title = f"● Status: Thinking... ({command[:16]})"
        try:
            action = parse(command)
            success, message = dispatch(action)
            output_response(
                message,
                action_name=action.action if success else None,
                speak_it=self._speech_enabled,
            )

            # Native macOS notification
            subtitle = action.action.replace("_", " ").title() if success else "Error"
            rumps.notification(
                title="Charlie",
                subtitle=subtitle,
                message=message,
            )
            self._update_last_result(message)
        except Exception as e:
            logger.error("Command execution error in menubar: %s", e)
            rumps.notification("Charlie", "Error", str(e))
        finally:
            self.title = "⚡ Charlie"
            self.status_item.title = "● Status: Ready"
            self.is_processing = False

    def _process_voice_worker(self) -> None:
        """Listen to microphone and process voice command."""
        from charlie.inputs.voice_input import listen_and_transcribe

        self.is_processing = True
        self.title = "🔴 Listening..."
        self.status_item.title = "● Status: Listening to mic..."
        try:
            rumps.notification("Charlie", "Voice Input", "Listening for your command now...")
            text = listen_and_transcribe()
            if not text:
                rumps.notification("Charlie", "Voice Input", "Didn't catch that. Please try again.")
                return

            self.title = "⚡ Thinking..."
            self.status_item.title = f"● Status: Heard '{text[:16]}'..."

            action = parse(text)
            success, message = dispatch(action)
            output_response(
                message,
                action_name=action.action if success else None,
                speak_it=self._speech_enabled,
            )

            subtitle = f"Heard: \"{text}\""
            rumps.notification(
                title="Charlie",
                subtitle=subtitle,
                message=message,
            )
            self._update_last_result(message)
        except Exception as e:
            logger.error("Voice processing error in menubar: %s", e)
            rumps.notification("Charlie", "Voice Error", str(e))
        finally:
            self.title = "⚡ Charlie"
            self.status_item.title = "● Status: Ready"
            self.is_processing = False

    def _on_wake_command_heard(self, command: str) -> None:
        """Callback invoked when background wake word listener detects a command."""
        self.title = "⚡ Thinking..."
        self.status_item.title = f"● Status: Wake word: '{command[:16]}'"
        try:
            action = parse(command)
            success, message = dispatch(action)
            output_response(
                message,
                action_name=action.action if success else None,
                speak_it=self._speech_enabled,
            )

            rumps.notification(
                title="Charlie (Wake Word)",
                subtitle=f"\"{command}\"",
                message=message,
            )
            self._update_last_result(message)
        finally:
            self.title = "⚡ Charlie"
            self.status_item.title = "● Status: Ready"


def run_menubar_app() -> None:
    """Launch Charlie menu bar application (Phase 4)."""
    app = CharlieMenuBarApp()
    app.run()


if __name__ == "__main__":
    run_menubar_app()
