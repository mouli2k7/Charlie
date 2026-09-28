"""Voice input handler for Charlie.

Implements push-to-talk listening using the MacBook Pro built-in microphone,
Google Speech Recognition with multi-language fallback (en-US / en-IN),
and sensitive microphone energy thresholds.

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
        _original_which = shutil.which

        def _patched_which(name: str, *args, **kwargs) -> Optional[str]:
            if name == "flac":
                return native_flac
            return _original_which(name, *args, **kwargs)

        shutil.which = _patched_which  # type: ignore[assignment]


_patch_flac()
# -------------------------------------------------------------------------


# SpeechRecognition recognizer instance
_recognizer = sr.Recognizer()
_recognizer.energy_threshold = 150       # Sensitive default for MacBook built-in mic
_recognizer.dynamic_energy_threshold = True
_recognizer.dynamic_energy_adjustment_damping = 0.15
_recognizer.dynamic_energy_ratio = 1.5
_recognizer.pause_threshold = 0.8        # seconds of silence to confirm end of speech
_recognizer.phrase_threshold = 0.2       # minimum seconds of speech before considering started
_recognizer.non_speaking_duration = 0.4

# Prefer the built-in MacBook Pro Microphone
PREFERRED_MIC_NAME = "MacBook Pro Microphone"

# Filler prefixes and phonetic variants to strip from the beginning of transcription
STRIP_PREFIXES = re.compile(
    r"^(?:hey|hi|hello|ok|okay|a)?\s*(?:charlie|charley|charly|sharlie)[,:\s-]*",
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


def _transcribe_audio(audio: sr.AudioData) -> Optional[str]:
    """Transcribe audio with multi-language fallback (e.g. en-US then en-IN)."""
    cfg = get_config()
    primary_lang = cfg.speech_language
    fallback_lang = "en-IN" if primary_lang != "en-IN" else "en-US"

    languages = [primary_lang, fallback_lang]

    for lang in languages:
        try:
            raw_text = _recognizer.recognize_google(audio, language=lang)
            if raw_text and raw_text.strip():
                return raw_text.strip()
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print(f"Speech recognition network error: {e}")
            return None
        except Exception:
            continue

    return None


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

    # Sync energy threshold with configuration
    _recognizer.energy_threshold = cfg.mic_energy_threshold

    try:
        with sr.Microphone(device_index=mic_index) as source:
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

    print("Transcribing...")
    text = _transcribe_audio(audio)

    if not text:
        print("Didn't catch that. Please speak clearly into the mic.")
        return None

    cleaned = _strip_wake_prefix(text)
    final_text = cleaned if cleaned else text
    print(f"Heard: {final_text}")
    return final_text
