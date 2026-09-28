"""Voice input handler for Charlie — Phase 2.

Implements push-to-talk listening using the MacBook Pro built-in microphone,
Google Speech Recognition for transcription, and graceful error handling
for mic issues, background noise, and network failures.

Apple Silicon fix: patches speech_recognition to use the native ARM64 flac
binary from Homebrew instead of the bundled Intel-only flac-mac binary.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Optional

import speech_recognition as sr

from charlie.config import get_config

# -------------------------------------------------------------------------
# Apple Silicon fix: replace the bundled Intel flac-mac with the Homebrew ARM64 one
# -------------------------------------------------------------------------
_HOMEBREW_FLAC_PATHS = [
    "/opt/homebrew/bin/flac",     # Apple Silicon Homebrew
    "/usr/local/bin/flac",        # Intel Homebrew (fallback)
]

def _patch_flac() -> None:
    """Patch speech_recognition's flac converter to use the native ARM64 binary."""
    native_flac = next(
        (p for p in _HOMEBREW_FLAC_PATHS if os.path.isfile(p) and os.access(p, os.X_OK)),
        None,
    )
    if native_flac:
        # Monkey-patch the module-level converter path used internally by AudioData
        try:
            import speech_recognition as _sr
            # Patch the flac_converter path the library resolves at runtime
            _sr.AudioData.get_flac_data.__globals__  # ensure accessible
        except Exception:
            pass
        # Override via shutil so `shutil.which("flac")` returns our binary
        _original_which = shutil.which

        def _patched_which(name: str, *args, **kwargs) -> Optional[str]:
            if name == "flac":
                return native_flac
            return _original_which(name, *args, **kwargs)

        shutil.which = _patched_which  # type: ignore[assignment]

_patch_flac()
# -------------------------------------------------------------------------


# SpeechRecognition recognizer instance (shared, not re-created per listen)
_recognizer = sr.Recognizer()
_recognizer.pause_threshold = 0.8      # seconds of silence = end of speech
_recognizer.non_speaking_duration = 0.4

# Prefer the built-in MacBook Pro Microphone
PREFERRED_MIC_NAME = "MacBook Pro Microphone"

# Filler prefixes to strip from the beginning of a transcription
STRIP_PREFIXES = re.compile(
    r"^(?:hey\s+charlie|ok\s+charlie|charlie)[,\s:]*",
    re.IGNORECASE,
)


def _get_mic_index() -> Optional[int]:
    """Return device index for the preferred mic; None = system default."""
    try:
        names = sr.Microphone.list_microphone_names()
        for i, name in enumerate(names):
            if PREFERRED_MIC_NAME.lower() in name.lower():
                return i
    except Exception:
        pass
    return None


def _strip_wake_prefix(text: str) -> str:
    """Remove leading 'Charlie' / 'Hey Charlie' wake phrase from transcript."""
    return STRIP_PREFIXES.sub("", text).strip()


def listen_and_transcribe(
    timeout: Optional[int] = None,
    phrase_limit: Optional[int] = None,
) -> Optional[str]:
    """Listen to the microphone and return transcribed text.

    Args:
        timeout: Seconds to wait for speech before giving up (None = wait forever).
        phrase_limit: Max seconds of continuous speech to record.

    Returns:
        Transcribed string, or None if nothing was understood or an error occurred.
    """
    cfg = get_config()
    listen_seconds = phrase_limit or cfg.voice_listen_seconds
    mic_index = _get_mic_index()

    try:
        with sr.Microphone(device_index=mic_index) as source:
            # Calibrate for ambient noise every call (~0.3s, silent)
            _recognizer.adjust_for_ambient_noise(source, duration=0.3)
            print("Listening... (speak now)")
            audio = _recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=listen_seconds,
            )
    except sr.WaitTimeoutError:
        print("No speech detected within timeout.")
        return None
    except OSError as e:
        print(f"Microphone error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected mic error: {e}")
        return None

    # Try Google Speech Recognition (requires internet)
    try:
        text = _recognizer.recognize_google(audio, language="en-IN")
        cleaned = _strip_wake_prefix(text)
        if cleaned:
            print(f"Heard: {cleaned}")
            return cleaned
        return None
    except sr.UnknownValueError:
        print("Didn't catch that. Please try again.")
        return None
    except sr.RequestError as e:
        print(f"Speech recognition service error: {e}")
        return None
    except Exception as e:
        print(f"Transcription error: {e}")
        return None
