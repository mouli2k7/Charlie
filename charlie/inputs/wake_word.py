"""Wake word detection for Charlie (Phase 3).

Listens in the background for 'Hey Charlie', 'Charlie', or 'Ok Charlie'.
Maintains a continuous open microphone stream to prevent audio clipping,
and supports multi-language transcription and phonetic wake variations.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable, Optional, Tuple

import speech_recognition as sr

from charlie.brain import parse
from charlie.config import get_config
from charlie.inputs.voice_input import (
    _get_mic_index,
    _transcribe_audio,
    listen_and_transcribe,
)
from charlie.output.speaker import output_response
from charlie.router import dispatch

logger = logging.getLogger(__name__)


def build_wake_pattern(wake_word: str = "hey charlie") -> re.Pattern:
    """Build a flexible regex pattern to detect the wake word and phonetic variants."""
    clean = wake_word.strip().lower()
    if "charlie" in clean:
        pattern_str = r"^\s*(?:hey|hi|hello|ok|okay|a)?\s*(?:charlie|charley|charly|sharlie)[,:\s-]*(.*)$"
    else:
        escaped = re.escape(clean)
        pattern_str = rf"^\s*(?:{escaped})[,:\s-]*(.*)$"
    return re.compile(pattern_str, re.IGNORECASE)


def extract_wake_command(text: str, wake_word: str = "hey charlie") -> Tuple[bool, str]:
    """Check if text begins with the wake word and extract any trailing command.

    Returns:
        (triggered, command_text)
        - triggered: True if the wake phrase was detected.
        - command_text: The remainder of the sentence after the wake phrase (or empty string).
    """
    if not text:
        return False, ""

    pattern = build_wake_pattern(wake_word)
    match = pattern.match(text.strip())
    if match:
        return True, match.group(1).strip()

    # Also handle wake word appended at the end (e.g. "open spotify charlie")
    if "charlie" in wake_word.lower():
        trailing_match = re.search(r"^(.*?)[,:\s]+(?:charlie|charley|charly)\s*$", text.strip(), re.IGNORECASE)
        if trailing_match and trailing_match.group(1).strip():
            return True, trailing_match.group(1).strip()

    return False, ""


class WakeWordListener:
    """Background listener that continuously monitors for the wake word with an open stream."""

    def __init__(
        self,
        on_command: Optional[Callable[[str], None]] = None,
        wake_word: Optional[str] = None,
    ) -> None:
        self.cfg = get_config()
        self.wake_word = wake_word or self.cfg.wake_word
        self.on_command = on_command or self._default_on_command
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = self.cfg.mic_energy_threshold
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.dynamic_energy_adjustment_damping = 0.15
        self._recognizer.dynamic_energy_ratio = 1.5
        self._recognizer.pause_threshold = 0.8
        self._recognizer.phrase_threshold = 0.2
        self._recognizer.non_speaking_duration = 0.3

    @property
    def is_running(self) -> bool:
        """Check if background listener is currently active."""
        return self._thread is not None and not self._stop_event.is_set()

    def start(self) -> None:
        """Start listening for the wake word in a background daemon thread."""
        if self.is_running:
            logger.info("Wake word listener is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="CharlieWakeWordListener",
        )
        self._thread.start()
        logger.info("Wake word listener started for '%s'", self.wake_word)

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the background listener thread."""
        if self._stop_event.is_set() and self._thread is None:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("Wake word listener stopped.")

    def _default_on_command(self, command_text: str) -> None:
        """Default handler: feed command into Charlie brain, router, and speaker."""
        print(f"\n[Charlie] Processing: '{command_text}'")
        action = parse(command_text)
        success, message = dispatch(action)
        output_response(message, action_name=action.action if success else None)

    def _listen_loop(self) -> None:
        """Continuous background listening loop keeping audio stream open."""
        mic_index = _get_mic_index()

        try:
            mic = sr.Microphone(device_index=mic_index)
        except Exception as e:
            logger.error("Failed to initialize microphone for wake word: %s", e)
            print(f"[Wake Word] Microphone initialization error: {e}")
            self._stop_event.set()
            return

        print(f"[Wake Word] Listening continuously for '{self.wake_word}' in background...")

        try:
            # KEEP STREAM OPEN: Enter context ONCE to avoid PyAudio stream open/close lag
            with mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                # Clamp threshold to ensure high sensitivity
                self._recognizer.energy_threshold = max(80, min(self._recognizer.energy_threshold, 250))

                while not self._stop_event.is_set():
                    try:
                        audio = self._recognizer.listen(
                            source,
                            timeout=1.0,
                            phrase_time_limit=6.0,
                        )
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        if not self._stop_event.is_set():
                            logger.debug("Wake word mic read error: %s", e)
                            time.sleep(0.1)
                        continue

                    if self._stop_event.is_set():
                        break

                    # Multi-language transcribe
                    text = _transcribe_audio(audio)
                    if not text:
                        continue

                    triggered, cmd = extract_wake_command(text, self.wake_word)
                    if not triggered:
                        continue

                    print(f"\n[Wake Word] Triggered! Heard: '{text}'")

                    # Trigger visual on-screen popup and audio chime
                    try:
                        from charlie.ui.popup import show_wake_popup
                        show_wake_popup(command=cmd)
                    except Exception as popup_err:
                        logger.debug("Failed to show wake popup: %s", popup_err)

                    if cmd:
                        self.on_command(cmd)
                    else:
                        output_response("Yes?", speak_it=self.cfg.speak_responses)
                        follow_up = listen_and_transcribe(timeout=6, phrase_limit=8)
                        if follow_up:
                            self.on_command(follow_up)
        except Exception as e:
            logger.error("Wake word listener loop error: %s", e)
        finally:
            self._stop_event.set()


_global_listener: Optional[WakeWordListener] = None


def get_wake_word_listener(
    on_command: Optional[Callable[[str], None]] = None,
) -> WakeWordListener:
    """Get or create the singleton WakeWordListener instance."""
    global _global_listener
    if _global_listener is None:
        _global_listener = WakeWordListener(on_command=on_command)
    elif on_command is not None:
        _global_listener.on_command = on_command
    return _global_listener


def start_wake_word_listener(
    on_command: Optional[Callable[[str], None]] = None,
) -> WakeWordListener:
    """Start background wake word listener."""
    listener = get_wake_word_listener(on_command=on_command)
    listener.start()
    return listener


def stop_wake_word_listener() -> None:
    """Stop active background wake word listener."""
    global _global_listener
    if _global_listener is not None:
        _global_listener.stop()
