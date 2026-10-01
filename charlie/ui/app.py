"""Native macOS Desktop GUI Application for Charlie (Phase 4).

Provides a modern, sleek, and responsive macOS window interface with:
- Live conversation stream and activity cards
- Interactive text command prompt
- Push-to-talk voice recording button
- Real-time status indicators (Listening, Thinking, Ready)
- Quick setting toggles (Wake Word, Spoken Voice, Voice selection, Launch at Login)
- Integrated macOS Menu Bar icon and Dock presence
"""

from __future__ import annotations

import logging
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from charlie import __version__
from charlie.brain import parse
from charlie.config import get_config, save_setting
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

# Dark mode color palette
BG_DARK = "#121316"
BG_CARD = "#1a1c23"
BG_INPUT = "#22252e"
BORDER_COLOR = "#2d313d"
ACCENT_CYAN = "#00e5ff"
ACCENT_PURPLE = "#a855f7"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"
STATUS_GREEN_BG = "#0f2d1e"
STATUS_GREEN_TXT = "#4ade80"
STATUS_RED_BG = "#3b1114"
STATUS_RED_TXT = "#f87171"
STATUS_BLUE_BG = "#0c2b45"
STATUS_BLUE_TXT = "#38bdf8"


class CharlieAppWindow:
    """Main macOS desktop GUI window for Charlie."""

    def __init__(self, root: tk.Tk, autostart_wake_word: bool = True) -> None:
        self.root = root
        self.cfg = get_config()
        self.autostart_wake_word = autostart_wake_word
        self.msg_queue: queue.Queue = queue.Queue()
        self.is_busy = False

        # Window setup
        self.root.title("Charlie")
        self.root.geometry("700x600")
        self.root.minsize(580, 500)
        self.root.configure(bg=BG_DARK)

        # Center on screen
        self._center_window(700, 600)

        # Setup custom styles and build UI
        self._setup_styles()
        self._build_header()
        self._build_chat_view()
        self._build_input_bar()
        self._build_controls()

        # Intercept window close to minimize to background
        self.root.protocol("WM_DELETE_WINDOW", self.on_minimize_to_tray)

        # Periodic queue checker for thread-safe UI updates
        self.root.after(50, self._process_queue)

        # Initialize native menu bar item in background
        self._setup_status_bar_menu()

        # Start single-instance IPC listener
        self._start_instance_listener()

        # macOS keybindings (Cmd+W hide, Cmd+Q quit)
        self.root.bind("<Command-w>", lambda e: self.on_minimize_to_tray())
        self.root.bind("<Command-q>", lambda e: self.on_full_quit())

        # Register macOS system hooks
        try:
            self.root.createcommand("::tk::mac::ReopenApplication", self.show_window)
            self.root.createcommand("::tk::mac::Quit", self.on_full_quit)
        except Exception:
            pass

        # Set process name and Dock icon image
        self._setup_macos_app_identity()

        # Bring window to front immediately
        self.show_window()

        # Auto-start wake word listener if requested
        if self.autostart_wake_word and self.cfg.wake_word_autostart:
            self._start_wake_word()

    def _setup_macos_app_identity(self) -> None:
        """Set process name and Dock icon using AppKit / Foundation."""
        try:
            from Foundation import NSProcessInfo

            NSProcessInfo.processInfo().setProcessName_("Charlie")
        except Exception:
            pass
        try:
            from AppKit import NSApplication, NSImage

            for icon_path in [
                os.path.expanduser("~/Documents/Charlie/Charlie.app/Contents/Resources/AppIcon.icns"),
                "/Applications/Charlie.app/Contents/Resources/AppIcon.icns",
            ]:
                if os.path.exists(icon_path):
                    img = NSImage.alloc().initWithContentsOfFile_(icon_path)
                    if img:
                        NSApplication.sharedApplication().setApplicationIconImage_(img)
                        break
        except Exception:
            pass

    def _center_window(self, width: int, height: int) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 40)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_CARD,
            foreground=TEXT_PRIMARY,
            darkcolor=BORDER_COLOR,
            lightcolor=BORDER_COLOR,
        )

    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=BG_DARK, padx=20, pady=16)
        header_frame.pack(fill=tk.X)

        title_box = tk.Frame(header_frame, bg=BG_DARK)
        title_box.pack(side=tk.LEFT)

        app_title = tk.Label(
            title_box,
            text="⚡ CHARLIE",
            font=("Helvetica", 18, "bold"),
            fg=ACCENT_CYAN,
            bg=BG_DARK,
        )
        app_title.pack(anchor="w")

        version_label = tk.Label(
            title_box,
            text=f"macOS AI Assistant • v{__version__}",
            font=("Helvetica", 11),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        version_label.pack(anchor="w")

        # Status badge (pill)
        self.status_badge = tk.Label(
            header_frame,
            text="● Initializing...",
            font=("Helvetica", 11, "bold"),
            fg=STATUS_GREEN_TXT,
            bg=STATUS_GREEN_BG,
            padx=12,
            pady=4,
            relief=tk.FLAT,
        )
        self.status_badge.pack(side=tk.RIGHT, pady=6)

    def _build_chat_view(self) -> None:
        # Container frame with border
        container = tk.Frame(
            self.root,
            bg=BG_CARD,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))

        # Text display area
        self.chat_text = tk.Text(
            container,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CYAN,
            selectbackground="#2e384d",
            selectforeground=TEXT_PRIMARY,
            font=("Helvetica", 13),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            state=tk.DISABLED,
        )
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(container, command=self.chat_text.yview, bg=BG_CARD)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.config(yscrollcommand=scrollbar.set)

        # Text styles
        self.chat_text.tag_config("user_label", foreground=ACCENT_CYAN, font=("Helvetica", 11, "bold"))
        self.chat_text.tag_config("user_text", foreground=TEXT_PRIMARY, font=("Helvetica", 13))
        self.chat_text.tag_config("bot_label", foreground=ACCENT_PURPLE, font=("Helvetica", 11, "bold"))
        self.chat_text.tag_config("bot_text", foreground=TEXT_PRIMARY, font=("Helvetica", 13))
        self.chat_text.tag_config("system_text", foreground=TEXT_MUTED, font=("Helvetica", 11, "italic"))

        # Welcome message
        self._append_system_message(
            "👋 Welcome to Charlie! You can say \"Hey Charlie\" anytime, click '🎙️ Speak', "
            "or type commands below.\nTry: \"what is the exchange rate of dollar to rupee\", "
            "\"open youtube\", or \"volume 50\"."
        )

    def _build_input_bar(self) -> None:
        bar_frame = tk.Frame(self.root, bg=BG_DARK, padx=20)
        bar_frame.pack(fill=tk.X, pady=(0, 10))

        # Entry container with rounded appearance
        entry_container = tk.Frame(
            bar_frame,
            bg=BG_INPUT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=10,
            pady=6,
        )
        entry_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.cmd_entry = tk.Entry(
            entry_container,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CYAN,
            font=("Helvetica", 13),
            relief=tk.FLAT,
        )
        self.cmd_entry.pack(fill=tk.X, expand=True)
        self.cmd_entry.bind("<Return>", lambda e: self.on_send_command())
        self.cmd_entry.focus_set()

        # Send Button
        send_btn = tk.Button(
            bar_frame,
            text="Send",
            font=("Helvetica", 12, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=7,
            cursor="pointinghand",
            command=self.on_send_command,
        )
        send_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Push-to-Talk Mic Button
        self.mic_btn = tk.Button(
            bar_frame,
            text="🎙️ Speak",
            font=("Helvetica", 12, "bold"),
            bg="#374151",
            fg="#ffffff",
            activebackground="#4b5563",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="pointinghand",
            command=self.on_mic_button,
        )
        self.mic_btn.pack(side=tk.LEFT)

    def _build_controls(self) -> None:
        ctrl_frame = tk.Frame(self.root, bg=BG_DARK, padx=20, pady=8)
        ctrl_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Wake Word Toggle Checkbox
        self.wake_var = tk.BooleanVar(value=False)
        self.wake_cb = tk.Checkbutton(
            ctrl_frame,
            text="⚡ 'Hey Charlie' Wake Word",
            variable=self.wake_var,
            font=("Helvetica", 11),
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            selectcolor=BG_CARD,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            command=self.on_toggle_wake_word,
        )
        self.wake_cb.pack(side=tk.LEFT, padx=(0, 14))

        # Spoken Voice Toggle Checkbox
        self.speech_var = tk.BooleanVar(value=self.cfg.speak_responses)
        self.speech_cb = tk.Checkbutton(
            ctrl_frame,
            text="🔊 Spoken Responses",
            variable=self.speech_var,
            font=("Helvetica", 11),
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            selectcolor=BG_CARD,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            command=self.on_toggle_speech,
        )
        self.speech_cb.pack(side=tk.LEFT, padx=(0, 14))

        # Launch at Login Checkbox
        self.login_var = tk.BooleanVar(value=is_launch_at_login_enabled())
        self.login_cb = tk.Checkbutton(
            ctrl_frame,
            text="🚀 Launch at Login",
            variable=self.login_var,
            font=("Helvetica", 11),
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            selectcolor=BG_CARD,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            command=self.on_toggle_login,
        )
        self.login_cb.pack(side=tk.LEFT, padx=(0, 14))

        # Voice Selector Combobox
        voice_label = tk.Label(
            ctrl_frame,
            text="Voice:",
            font=("Helvetica", 11),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        voice_label.pack(side=tk.LEFT, padx=(10, 4))

        self.voice_var = tk.StringVar(value=self.cfg.voice_name or "Samantha")
        voices = ["Samantha", "Daniel", "Karen", "Rishi", "Tara", "Alex"]
        self.voice_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.voice_var,
            values=voices,
            state="readonly",
            width=10,
        )
        self.voice_combo.pack(side=tk.LEFT)
        self.voice_combo.bind("<<ComboboxSelected>>", self.on_voice_selected)

        # Clear button
        clear_btn = tk.Button(
            ctrl_frame,
            text="🧹 Clear",
            font=("Helvetica", 10),
            bg=BG_DARK,
            fg=TEXT_MUTED,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            command=self.on_clear_chat,
        )
        clear_btn.pack(side=tk.RIGHT)

    def _setup_status_bar_menu(self) -> None:
        """Create native macOS menu bar status item using PyObjC AppKit."""
        try:
            from AppKit import (
                NSMenu,
                NSMenuItem,
                NSObject,
                NSStatusBar,
                NSVariableStatusItemLength,
            )

            class MenuActionHandler(NSObject):
                app_ref = None

                def onOpenWindow_(self, sender):
                    if self.app_ref:
                        self.app_ref.show_window()

                def onPushToTalk_(self, sender):
                    if self.app_ref:
                        self.app_ref.root.after(0, self.app_ref.on_mic_button)

                def onQuit_(self, sender):
                    if self.app_ref:
                        self.app_ref.on_full_quit()

            handler = MenuActionHandler.alloc().init()
            handler.app_ref = self

            menu = NSMenu.alloc().init()

            open_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "⚡ Open Charlie Window", "onOpenWindow:", "o"
            )
            open_item.setTarget_(handler)
            menu.addItem_(open_item)

            talk_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "🎙️ Voice Command (Push-to-Talk)", "onPushToTalk:", "v"
            )
            talk_item.setTarget_(handler)
            menu.addItem_(talk_item)

            menu.addItem_(NSMenuItem.separatorItem())

            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Charlie", "onQuit:", "q"
            )
            quit_item.setTarget_(handler)
            menu.addItem_(quit_item)

            status_bar = NSStatusBar.systemStatusBar()
            self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
            self._status_item.button().setTitle_("⚡ Charlie")
            self._status_item.setMenu_(menu)
            self._menu_handler = handler  # Keep reference alive
        except Exception as err:
            logger.debug("Menu bar item creation skipped: %s", err)

    def _start_instance_listener(self) -> None:
        """Listen on local Unix domain socket for IPC commands (e.g. SHOW)."""
        sock_path = os.path.expanduser("~/.charlie/charlie.sock")
        os.makedirs(os.path.dirname(sock_path), exist_ok=True)
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except Exception:
                pass
        try:
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(sock_path)
            server.listen(5)
            self._ipc_server = server
            self._sock_path = sock_path
        except Exception as err:
            logger.debug("Could not bind instance socket: %s", err)
            return

        def listen_loop():
            while getattr(self, "_ipc_server", None):
                try:
                    conn, _ = server.accept()
                    data = conn.recv(64)
                    if b"SHOW" in data:
                        self.root.after(0, self.show_window)
                    conn.close()
                except Exception:
                    break

        threading.Thread(target=listen_loop, daemon=True, name="CharlieIPCListener").start()

    def show_window(self) -> None:
        """Bring the application window forward, active, and focused."""
        try:
            self.root.deiconify()
        except Exception:
            pass
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after_idle(self.root.attributes, "-topmost", False)
        self.root.focus_force()
        if hasattr(self, "cmd_entry"):
            self.cmd_entry.focus_set()
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyRegular

            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            app.activateIgnoringOtherApps_(True)
        except Exception:
            pass

    def on_minimize_to_tray(self) -> None:
        """Hide window to background instead of terminating listener."""
        self.root.withdraw()
        try:
            # Show a native macOS banner confirming background operation
            subprocess.Popen([
                "osascript", "-e",
                'display notification "Charlie is active in the background. Click the ⚡ menu bar icon or Dock icon to reopen." with title "Charlie"'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def on_full_quit(self) -> None:
        """Completely shut down Charlie."""
        if hasattr(self, "_ipc_server") and self._ipc_server:
            try:
                self._ipc_server.close()
                self._ipc_server = None
            except Exception:
                pass
        if hasattr(self, "_sock_path") and self._sock_path:
            try:
                if os.path.exists(self._sock_path):
                    os.remove(self._sock_path)
            except Exception:
                pass
        try:
            stop_wake_word_listener()
        except Exception:
            pass
        self.root.destroy()
        sys.exit(0)

    def _set_status(self, text: str, state: str = "green") -> None:
        colors = {
            "green": (STATUS_GREEN_TXT, STATUS_GREEN_BG),
            "red": (STATUS_RED_TXT, STATUS_RED_BG),
            "blue": (STATUS_BLUE_TXT, STATUS_BLUE_BG),
            "muted": (TEXT_MUTED, BG_CARD),
        }
        fg, bg = colors.get(state, (STATUS_GREEN_TXT, STATUS_GREEN_BG))
        self.status_badge.config(text=text, fg=fg, bg=bg)

    def _append_user_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, "YOU\n", "user_label")
        self.chat_text.insert(tk.END, f"{text}\n\n", "user_text")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _append_bot_message(self, text: str, action_name: Optional[str] = None) -> None:
        self.chat_text.config(state=tk.NORMAL)
        label = f"CHARLIE ({action_name})\n" if action_name and action_name not in ("answer", "unknown") else "CHARLIE\n"
        self.chat_text.insert(tk.END, label, "bot_label")
        self.chat_text.insert(tk.END, f"{text}\n\n", "bot_text")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _append_system_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"{text}\n\n", "system_text")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _process_queue(self) -> None:
        """Process thread-safe updates."""
        try:
            while True:
                msg_type, payload = self.msg_queue.get_nowait()
                if msg_type == "user":
                    self._append_user_message(payload)
                elif msg_type == "bot":
                    text, action_name = payload
                    self._append_bot_message(text, action_name)
                elif msg_type == "system":
                    self._append_system_message(payload)
                elif msg_type == "status":
                    text, state = payload
                    self._set_status(text, state)
                elif msg_type == "mic_btn":
                    text, bg = payload
                    self.mic_btn.config(text=text, bg=bg)
                elif msg_type == "wake_state":
                    self.wake_var.set(payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._process_queue)

    def on_send_command(self) -> None:
        """Process typed command."""
        text = self.cmd_entry.get().strip()
        if not text or self.is_busy:
            return
        self.cmd_entry.delete(0, tk.END)
        self._execute_command_async(text)

    def on_mic_button(self) -> None:
        """Trigger push-to-talk voice recording in background."""
        if self.is_busy:
            return
        threading.Thread(
            target=self._voice_record_worker,
            daemon=True,
            name="CharlieUIVoiceWorker",
        ).start()

    def _voice_record_worker(self) -> None:
        from charlie.inputs.voice_input import listen_and_transcribe

        self.is_busy = True
        self.msg_queue.put(("status", ("🔴 Listening...", "red")))
        self.msg_queue.put(("mic_btn", ("🔴 Listening...", "#dc2626")))

        try:
            text = listen_and_transcribe()
            if not text:
                self.msg_queue.put(("status", ("Didn't catch that", "muted")))
                self.msg_queue.put(("system", "⚠️ Didn't catch that. Please try speaking again."))
                return

            self.msg_queue.put(("status", ("⚡ Thinking...", "blue")))
            self.msg_queue.put(("user", text))

            action = parse(text)
            success, message = dispatch(action)
            output_response(
                message,
                action_name=action.action if success else None,
                speak_it=self.speech_var.get(),
            )
            self.msg_queue.put(("bot", (message, action.action if success else None)))
        except Exception as err:
            logger.error("Error in voice worker: %s", err)
            self.msg_queue.put(("system", f"Error: {err}"))
        finally:
            self.is_busy = False
            self.msg_queue.put(("mic_btn", ("🎙️ Speak", "#374151")))
            is_listening = self.wake_var.get()
            status_text = '🟢 Listening for "Hey Charlie"' if is_listening else "● Ready"
            self.msg_queue.put(("status", (status_text, "green" if is_listening else "muted")))

    def _execute_command_async(self, text: str) -> None:
        """Run command parsing and dispatching in background."""
        self.is_busy = True
        self._append_user_message(text)
        self._set_status("⚡ Thinking...", "blue")

        def worker():
            try:
                action = parse(text)
                success, message = dispatch(action)
                output_response(
                    message,
                    action_name=action.action if success else None,
                    speak_it=self.speech_var.get(),
                )
                self.msg_queue.put(("bot", (message, action.action if success else None)))
            except Exception as err:
                logger.error("Error processing command: %s", err)
                self.msg_queue.put(("system", f"Error: {err}"))
            finally:
                self.is_busy = False
                is_listening = self.wake_var.get()
                status_text = '🟢 Listening for "Hey Charlie"' if is_listening else "● Ready"
                self.msg_queue.put(("status", (status_text, "green" if is_listening else "muted")))

        threading.Thread(target=worker, daemon=True, name="CharlieUICommandWorker").start()

    def _start_wake_word(self) -> None:
        listener = get_wake_word_listener()
        if not listener.is_running:
            start_wake_word_listener(on_command=self._on_wake_command_heard)
        self.wake_var.set(True)
        self._set_status('🟢 Listening for "Hey Charlie"', "green")

    def _stop_wake_word(self) -> None:
        stop_wake_word_listener()
        self.wake_var.set(False)
        self._set_status("● Wake Word Inactive", "muted")

    def on_toggle_wake_word(self) -> None:
        if self.wake_var.get():
            self._start_wake_word()
        else:
            self._stop_wake_word()

    def _on_wake_command_heard(self, command: str) -> None:
        """Callback from background wake listener."""
        self.msg_queue.put(("user", f"⚡ [Hey Charlie] {command}"))
        self.msg_queue.put(("status", ("⚡ Thinking...", "blue")))
        try:
            action = parse(command)
            success, message = dispatch(action)
            output_response(
                message,
                action_name=action.action if success else None,
                speak_it=self.speech_var.get(),
            )
            self.msg_queue.put(("bot", (message, action.action if success else None)))
        finally:
            is_listening = self.wake_var.get()
            status_text = '🟢 Listening for "Hey Charlie"' if is_listening else "● Ready"
            self.msg_queue.put(("status", (status_text, "green" if is_listening else "muted")))

    def on_toggle_speech(self) -> None:
        self.cfg.speak_responses = self.speech_var.get()
        save_setting("speak_responses", self.speech_var.get())

    def on_toggle_login(self) -> None:
        new_state = toggle_launch_at_login()
        self.login_var.set(new_state)

    def on_voice_selected(self, event=None) -> None:
        voice = self.voice_var.get()
        self.cfg.voice_name = voice
        save_setting("voice_name", voice)
        output_response(
            f"Hello, my voice is now set to {voice}.",
            speak_it=self.speech_var.get(),
            voice=voice,
        )

    def on_clear_chat(self) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state=tk.DISABLED)


def check_or_notify_existing_instance() -> bool:
    """If an existing Charlie instance is running, notify it to show its window and return True."""
    sock_path = os.path.expanduser("~/.charlie/charlie.sock")
    if not os.path.exists(sock_path):
        return False
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(1.5)
        client.connect(sock_path)
        client.sendall(b"SHOW\n")
        client.close()
        logger.info("Notified running Charlie instance to bring window forward.")
        return True
    except Exception:
        try:
            os.remove(sock_path)
        except Exception:
            pass
        return False


def run_charlie_app(autostart_wake_word: bool = True) -> None:
    """Launch Charlie native macOS desktop GUI app."""
    if check_or_notify_existing_instance():
        print("Charlie is already running; brought existing window to the front.")
        return

    root = tk.Tk()
    app = CharlieAppWindow(root, autostart_wake_word=autostart_wake_word)
    root.mainloop()


if __name__ == "__main__":
    run_charlie_app()
