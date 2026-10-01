"""Native macOS Desktop GUI Application for Charlie (Phase 4).

Provides a modern, sleek, and curved macOS window interface with:
- Curved pill status badges and responsive activity indicators
- Rounded input capsule with electric cyan focus border
- Modern high-contrast rounded pill buttons (Send, Speak, Voice, Clear)
- Native macOS popup voice selector with high-contrast readable options
- Live conversation stream with spacious modern chat bubbles
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

# Premium Dark Apple Color Palette
BG_DARK = "#0d0f15"         # Deep rich midnight background
BG_CARD = "#151822"         # Elevated surface for conversation
BG_INPUT = "#1a1e2a"        # Soft capsule background
BORDER_SUBTLE = "#262b3a"   # Subtle divider lines
BORDER_FOCUS = "#00e5ff"    # Vibrant electric cyan accent
ACCENT_CYAN = "#00e5ff"
ACCENT_PURPLE = "#a855f7"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"


class RoundedButton(tk.Canvas):
    """Custom high-contrast curved pill button with smooth hover and click states."""

    def __init__(
        self,
        parent,
        text: str,
        command=None,
        radius: int = 14,
        bg_color: str = "#2563eb",
        hover_color: str = "#3b82f6",
        active_color: Optional[str] = None,
        fg_color: str = "#ffffff",
        border_color: Optional[str] = None,
        border_width: int = 1,
        padx: int = 16,
        pady: int = 7,
        font=("Helvetica", 12, "bold"),
        **kwargs,
    ) -> None:
        super().__init__(parent, highlightthickness=0, bg=parent["bg"], **kwargs)
        self.text = text
        self.command = command
        self.radius = radius
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.active_color = active_color or hover_color
        self.fg_color = fg_color
        self.border_color = border_color or bg_color
        self.border_width = border_width
        self.btn_font = font
        self.padx = padx
        self.pady = pady
        self.is_hovered = False

        self._recompute_size()
        self._draw(self.bg_color)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.config(cursor="pointinghand")

    def _recompute_size(self) -> None:
        dummy = tk.Label(self.master, text=self.text, font=self.btn_font)
        w = dummy.winfo_reqwidth() + self.padx * 2
        h = dummy.winfo_reqheight() + self.pady * 2
        dummy.destroy()
        self.config(width=w, height=h)

    def _draw_rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        self.delete("all")
        # 4 corner arcs
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline=outline, width=self.border_width)
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline=outline, width=self.border_width)
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline=outline, width=self.border_width)
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline=outline, width=self.border_width)
        # Inner rectangles
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill)
        # Border connector lines
        if outline != fill and self.border_width > 0:
            self.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=self.border_width)
            self.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=self.border_width)
            self.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=self.border_width)
            self.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=self.border_width)

    def _draw(self, current_bg: str) -> None:
        try:
            w = int(self["width"])
            h = int(self["height"])
        except Exception:
            return
        r = min(self.radius, h // 2, w // 2)
        pad = self.border_width
        outline = self.border_color if self.border_color else current_bg
        self._draw_rounded_rect(pad, pad, w - pad, h - pad, r, current_bg, outline)
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg_color, font=self.btn_font)

    def _on_enter(self, event) -> None:
        self.is_hovered = True
        self._draw(self.hover_color)

    def _on_leave(self, event) -> None:
        self.is_hovered = False
        self._draw(self.bg_color)

    def _on_press(self, event) -> None:
        self._draw(self.active_color)

    def _on_release(self, event) -> None:
        self._draw(self.hover_color if self.is_hovered else self.bg_color)
        if self.is_hovered and self.command:
            self.command()

    def set_text_and_colors(
        self,
        text: Optional[str] = None,
        bg: Optional[str] = None,
        hover: Optional[str] = None,
        fg: Optional[str] = None,
        border: Optional[str] = None,
    ) -> None:
        """Update button label and color theme dynamically."""
        if text is not None:
            self.text = text
        if bg is not None:
            self.bg_color = bg
        if hover is not None:
            self.hover_color = hover
        if fg is not None:
            self.fg_color = fg
        if border is not None:
            self.border_color = border

        self._recompute_size()
        self._draw(self.hover_color if self.is_hovered else self.bg_color)


class RoundedPillBadge(tk.Canvas):
    """Sleek curved pill status indicator in the app header."""

    def __init__(
        self,
        parent,
        text: str = "● Initializing...",
        state: str = "green",
        radius: int = 13,
        **kwargs,
    ) -> None:
        super().__init__(parent, highlightthickness=0, bg=parent["bg"], **kwargs)
        self.text = text
        self.state = state
        self.radius = radius
        self.font = ("Helvetica", 11, "bold")
        self._resize_and_draw()

    def _get_colors(self, state: str):
        palette = {
            "green": ("#34d399", "#063b27", "#0f766e"),   # Emerald on dark forest
            "red": ("#fca5a5", "#450a0a", "#b91c1c"),     # Light red on dark crimson
            "blue": ("#38bdf8", "#082f49", "#0284c7"),    # Sky blue on dark cyan
            "muted": ("#94a3b8", "#1e2230", "#334155"),   # Slate on dark graphite
        }
        return palette.get(state, palette["green"])

    def _resize_and_draw(self) -> None:
        fg, bg, border = self._get_colors(self.state)
        dummy = tk.Label(self.master, text=self.text, font=self.font)
        w = dummy.winfo_reqwidth() + 24
        h = dummy.winfo_reqheight() + 10
        dummy.destroy()

        self.config(width=w, height=h)
        self.delete("all")
        r = min(self.radius, h // 2 - 1)

        # 4 arcs
        self.create_arc(1, 1, 1 + 2 * r, 1 + 2 * r, start=90, extent=90, fill=bg, outline=border)
        self.create_arc(w - 1 - 2 * r, 1, w - 1, 1 + 2 * r, start=0, extent=90, fill=bg, outline=border)
        self.create_arc(w - 1 - 2 * r, h - 1 - 2 * r, w - 1, h - 1, start=270, extent=90, fill=bg, outline=border)
        self.create_arc(1, h - 1 - 2 * r, 1 + 2 * r, h - 1, start=180, extent=90, fill=bg, outline=border)
        # Rectangles
        self.create_rectangle(1 + r, 1, w - 1 - r, h - 1, fill=bg, outline=bg)
        self.create_rectangle(1, 1 + r, w - 1, h - 1 - r, fill=bg, outline=bg)
        # Connectors
        self.create_line(1 + r, 1, w - 1 - r, 1, fill=border)
        self.create_line(1 + r, h - 1, w - 1 - r, h - 1, fill=border)
        self.create_line(1, 1 + r, 1, h - 1 - r, fill=border)
        self.create_line(w - 1, 1 + r, w - 1, h - 1 - r, fill=border)

        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self.font)

    def set_status(self, text: str, state: str = "green") -> None:
        self.text = text
        self.state = state
        self._resize_and_draw()


class RoundedInputCapsule(tk.Frame):
    """Modern curved pill container for text input with focus glow."""

    def __init__(
        self,
        parent,
        on_submit,
        bg_color: str = "#1a1e2a",
        border_color: str = "#2e3547",
        focus_border: str = "#00e5ff",
        radius: int = 16,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=parent["bg"], **kwargs)
        self.on_submit = on_submit
        self.bg_color = bg_color
        self.border_color = border_color
        self.focus_border = focus_border
        self.radius = radius
        self.is_focused = False

        self.canvas = tk.Canvas(self, bg=parent["bg"], highlightthickness=0, height=42)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(
            self.canvas,
            bg=bg_color,
            fg="#f8fafc",
            insertbackground="#00e5ff",
            font=("Helvetica", 13),
            relief=tk.FLAT,
            bd=0,
        )
        self.window_id = self.canvas.create_window(18, 21, window=self.entry, anchor="w")

        self.canvas.bind("<Configure>", self._on_resize)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Return>", lambda e: self.on_submit())

    def _draw(self) -> None:
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 20 or h < 20:
            return
        self.canvas.delete("capsule_shape")
        r = min(self.radius, h // 2 - 2)
        border = self.focus_border if self.is_focused else self.border_color
        b_width = 2 if self.is_focused else 1

        # 4 arcs
        self.canvas.create_arc(2, 2, 2 + 2 * r, 2 + 2 * r, start=90, extent=90, fill=self.bg_color, outline=border, width=b_width, tags="capsule_shape")
        self.canvas.create_arc(w - 2 - 2 * r, 2, w - 2, 2 + 2 * r, start=0, extent=90, fill=self.bg_color, outline=border, width=b_width, tags="capsule_shape")
        self.canvas.create_arc(w - 2 - 2 * r, h - 2 - 2 * r, w - 2, h - 2, start=270, extent=90, fill=self.bg_color, outline=border, width=b_width, tags="capsule_shape")
        self.canvas.create_arc(2, h - 2 - 2 * r, 2 + 2 * r, h - 2, start=180, extent=90, fill=self.bg_color, outline=border, width=b_width, tags="capsule_shape")
        # Rectangles
        self.canvas.create_rectangle(2 + r, 2, w - 2 - r, h - 2, fill=self.bg_color, outline=self.bg_color, tags="capsule_shape")
        self.canvas.create_rectangle(2, 2 + r, w - 2, h - 2 - r, fill=self.bg_color, outline=self.bg_color, tags="capsule_shape")
        # Connectors
        self.canvas.create_line(2 + r, 2, w - 2 - r, 2, fill=border, width=b_width, tags="capsule_shape")
        self.canvas.create_line(2 + r, h - 2, w - 2 - r, h - 2, fill=border, width=b_width, tags="capsule_shape")
        self.canvas.create_line(2, 2 + r, 2, h - 2 - r, fill=border, width=b_width, tags="capsule_shape")
        self.canvas.create_line(w - 2, 2 + r, w - 2, h - 2 - r, fill=border, width=b_width, tags="capsule_shape")

        self.canvas.tag_lower("capsule_shape")
        self.canvas.coords(self.window_id, r + 6, h // 2)
        entry_w = max(10, (w - 2 * r - 24) // 8)
        self.entry.config(width=entry_w)

    def _on_resize(self, event) -> None:
        self._draw()

    def _on_focus_in(self, event) -> None:
        self.is_focused = True
        self._draw()

    def _on_focus_out(self, event) -> None:
        self.is_focused = False
        self._draw()

    def get(self) -> str:
        return self.entry.get()

    def delete(self, first, last=None) -> None:
        self.entry.delete(first, last)

    def focus_set(self) -> None:
        self.entry.focus_set()


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
        self.root.geometry("720x620")
        self.root.minsize(600, 520)
        self.root.configure(bg=BG_DARK)

        # Center on screen
        self._center_window(720, 620)

        # Build UI components
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

    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=BG_DARK, padx=22, pady=16)
        header_frame.pack(fill=tk.X)

        title_box = tk.Frame(header_frame, bg=BG_DARK)
        title_box.pack(side=tk.LEFT)

        app_title = tk.Label(
            title_box,
            text="⚡ CHARLIE",
            font=("Helvetica", 19, "bold"),
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

        # Curved Status Badge
        self.status_badge = RoundedPillBadge(
            header_frame,
            text="● Initializing...",
            state="green",
            radius=13,
        )
        self.status_badge.pack(side=tk.RIGHT, pady=4)

    def _build_chat_view(self) -> None:
        # Container frame with curved aesthetic
        container = tk.Frame(
            self.root,
            bg=BG_CARD,
            highlightbackground="#232736",
            highlightthickness=1,
            padx=12,
            pady=12,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=22, pady=(0, 12))

        # Text display area
        self.chat_text = tk.Text(
            container,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CYAN,
            selectbackground="#2563eb",
            selectforeground="#ffffff",
            font=("Helvetica", 13),
            wrap=tk.WORD,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=10,
            state=tk.DISABLED,
        )
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(container, command=self.chat_text.yview, bg=BG_CARD)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.config(yscrollcommand=scrollbar.set)

        # Bubble-like typography with comfortable padding
        self.chat_text.tag_config(
            "user_label",
            foreground=ACCENT_CYAN,
            font=("Helvetica", 11, "bold"),
            lmargin1=14,
            lmargin2=14,
            spacing1=6,
            spacing3=2,
        )
        self.chat_text.tag_config(
            "user_text",
            foreground="#ffffff",
            font=("Helvetica", 13),
            lmargin1=14,
            lmargin2=14,
            spacing1=2,
            spacing3=8,
        )
        self.chat_text.tag_config(
            "bot_label",
            foreground="#c084fc",
            font=("Helvetica", 11, "bold"),
            lmargin1=14,
            lmargin2=14,
            spacing1=6,
            spacing3=2,
        )
        self.chat_text.tag_config(
            "bot_text",
            foreground="#f1f5f9",
            font=("Helvetica", 13),
            lmargin1=14,
            lmargin2=14,
            spacing1=2,
            spacing3=8,
        )
        self.chat_text.tag_config(
            "system_text",
            foreground="#94a3b8",
            font=("Helvetica", 11, "italic"),
            lmargin1=14,
            lmargin2=14,
            spacing1=4,
            spacing3=8,
        )

        # Welcome message
        self._append_system_message(
            "👋 Welcome to Charlie! You can say \"Hey Charlie\" anytime, click '🎙️ Speak', "
            "or type commands below.\nTry: \"what is the exchange rate of dollar to rupee\", "
            "\"open youtube\", or \"volume 50\"."
        )

    def _build_input_bar(self) -> None:
        bar_frame = tk.Frame(self.root, bg=BG_DARK, padx=22)
        bar_frame.pack(fill=tk.X, pady=(0, 10))

        # Curved input capsule
        self.input_capsule = RoundedInputCapsule(
            bar_frame,
            on_submit=self.on_send_command,
            bg_color=BG_INPUT,
            border_color="#2e3547",
            focus_border="#00e5ff",
            radius=16,
        )
        self.input_capsule.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.cmd_entry = self.input_capsule.entry
        self.cmd_entry.focus_set()

        # Curved Send Button (Electric Blue pill with bold white text)
        self.send_btn = RoundedButton(
            bar_frame,
            text="Send ➔",
            command=self.on_send_command,
            radius=15,
            bg_color="#2563eb",
            hover_color="#3b82f6",
            fg_color="#ffffff",
            border_color="#3b82f6",
            padx=18,
            pady=8,
            font=("Helvetica", 12, "bold"),
        )
        self.send_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Curved Push-to-Talk Mic Button (Dark slate pill with cyan border)
        self.mic_btn = RoundedButton(
            bar_frame,
            text="🎙️ Speak",
            command=self.on_mic_button,
            radius=15,
            bg_color="#1e293b",
            hover_color="#334155",
            fg_color="#f8fafc",
            border_color="#38bdf8",
            padx=16,
            pady=8,
            font=("Helvetica", 12, "bold"),
        )
        self.mic_btn.pack(side=tk.LEFT)

    def _build_controls(self) -> None:
        ctrl_frame = tk.Frame(self.root, bg=BG_DARK, padx=22, pady=10)
        ctrl_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Wake Word Toggle Checkbox
        self.wake_var = tk.BooleanVar(value=False)
        self.wake_cb = tk.Checkbutton(
            ctrl_frame,
            text="⚡ 'Hey Charlie' Wake Word",
            variable=self.wake_var,
            font=("Helvetica", 11),
            fg="#e2e8f0",
            bg=BG_DARK,
            selectcolor="#2563eb",
            activebackground=BG_DARK,
            activeforeground="#38bdf8",
            command=self.on_toggle_wake_word,
            cursor="pointinghand",
        )
        self.wake_cb.pack(side=tk.LEFT, padx=(0, 14))

        # Spoken Voice Toggle Checkbox
        self.speech_var = tk.BooleanVar(value=self.cfg.speak_responses)
        self.speech_cb = tk.Checkbutton(
            ctrl_frame,
            text="🔊 Spoken Responses",
            variable=self.speech_var,
            font=("Helvetica", 11),
            fg="#e2e8f0",
            bg=BG_DARK,
            selectcolor="#2563eb",
            activebackground=BG_DARK,
            activeforeground="#38bdf8",
            command=self.on_toggle_speech,
            cursor="pointinghand",
        )
        self.speech_cb.pack(side=tk.LEFT, padx=(0, 14))

        # Launch at Login Checkbox
        self.login_var = tk.BooleanVar(value=is_launch_at_login_enabled())
        self.login_cb = tk.Checkbutton(
            ctrl_frame,
            text="🚀 Launch at Login",
            variable=self.login_var,
            font=("Helvetica", 11),
            fg="#e2e8f0",
            bg=BG_DARK,
            selectcolor="#2563eb",
            activebackground=BG_DARK,
            activeforeground="#38bdf8",
            command=self.on_toggle_login,
            cursor="pointinghand",
        )
        self.login_cb.pack(side=tk.LEFT, padx=(0, 14))

        # Voice Selector Curved Button with Native macOS Popup Menu
        curr_voice = self.cfg.voice_name or "Samantha"
        self.voice_var = tk.StringVar(value=curr_voice)
        self.voice_btn = RoundedButton(
            ctrl_frame,
            text=f"🗣️ Voice: {curr_voice} ▾",
            command=self.on_open_voice_menu,
            radius=13,
            bg_color="#1e2430",
            hover_color="#2b3242",
            fg_color="#38bdf8",
            border_color="#3b4252",
            padx=12,
            pady=5,
            font=("Helvetica", 11, "bold"),
        )
        self.voice_btn.pack(side=tk.LEFT, padx=(6, 0))

        # Clear Button
        self.clear_btn = RoundedButton(
            ctrl_frame,
            text="🧹 Clear",
            command=self.on_clear_chat,
            radius=13,
            bg_color="#1e2430",
            hover_color="#2b3242",
            fg_color="#94a3b8",
            border_color="#3b4252",
            padx=12,
            pady=5,
            font=("Helvetica", 11),
        )
        self.clear_btn.pack(side=tk.RIGHT)

    def on_open_voice_menu(self) -> None:
        """Open native macOS popup menu with available voices."""
        menu = tk.Menu(self.root, tearoff=0)
        voices = [
            ("Samantha", "Samantha (US Female, Siri-like)"),
            ("Daniel", "Daniel (UK Male, Jarvis-like)"),
            ("Karen", "Karen (Australian Female)"),
            ("Rishi", "Rishi (Indian English Male)"),
            ("Tara", "Tara (Indian English Female)"),
            ("Alex", "Alex (Classic macOS Male)"),
        ]
        for v_id, label in voices:
            menu.add_radiobutton(
                label=label,
                value=v_id,
                variable=self.voice_var,
                command=lambda v=v_id: self.select_voice(v),
            )
        # Position menu directly below the voice button
        x = self.voice_btn.winfo_rootx()
        y = self.voice_btn.winfo_rooty() + self.voice_btn.winfo_height() + 2
        menu.tk_popup(x, y)

    def select_voice(self, voice_name: str) -> None:
        """Select active voice, update button, and play preview."""
        self.voice_var.set(voice_name)
        self.cfg.voice_name = voice_name
        save_setting("voice_name", voice_name)
        self.voice_btn.set_text_and_colors(text=f"🗣️ Voice: {voice_name} ▾")
        output_response(
            f"Hello, my voice is now set to {voice_name}.",
            speak_it=self.speech_var.get(),
            voice=voice_name,
        )

    def on_voice_selected(self, event=None) -> None:
        self.select_voice(self.voice_var.get())

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
        self.status_badge.set_status(text, state)

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
                    state, _ = payload
                    if state == "listening":
                        self.mic_btn.set_text_and_colors(
                            text="🔴 Listening...",
                            bg="#dc2626",
                            hover="#ef4444",
                            fg="#ffffff",
                            border="#f87171",
                        )
                    else:
                        self.mic_btn.set_text_and_colors(
                            text="🎙️ Speak",
                            bg="#1e293b",
                            hover="#334155",
                            fg="#f8fafc",
                            border="#38bdf8",
                        )
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
        self.msg_queue.put(("mic_btn", ("listening", None)))

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
            self.msg_queue.put(("mic_btn", ("normal", None)))
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
