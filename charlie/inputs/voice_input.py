"""Voice input handler for Charlie.

Implements push-to-talk listening using the MacBook Pro built-in microphone,
Google Speech Recognition with multi-language fallback (en-US / en-IN),
and sensitive microphone energy thresholds.

Apple Silicon fix: patches speech_recognition to use the native ARM64 flac
binary from Homebrew instead of the bundled Intel-only flac-mac binary.
"""

from __future__ import annotations

import concurrent.futures
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
_recognizer.dynamic_energy_ratio = 1.3
_recognizer.pause_threshold = 0.5        # Lowered to 0.5s for fast speech completion
_recognizer.phrase_threshold = 0.15      # Minimum seconds before speech starts
_recognizer.non_speaking_duration = 0.2

# Prefer the built-in MacBook Pro Microphone
PREFERRED_MIC_NAME = "MacBook Pro Microphone"

# Filler prefixes and phonetic variants to strip from the beginning of transcription
WAKE_NAME_VARIANTS = (
    r"(?:charlie|charley|charly|charli|charlee|charle|charl|char|"
    r"sharlie|sharli|sharly|cherry|jolly|curly|carly|karli|karly|"
    r"harley|chaley|chali|challie)"
)
GREETING_VARIANTS = r"(?:hey|hay|he|hi|hai|hello|hallo|ok|okay|yo|ay|a|eh|uh|um|so|please|can\s+you)?"

STRIP_PREFIXES = re.compile(
    rf"^\s*(?:{GREETING_VARIANTS}\s+)?{WAKE_NAME_VARIANTS}[,:\s-]*",
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


def _transcribe_audio_candidates(
    audio: sr.AudioData,
    recognizer: Optional[sr.Recognizer] = None,
) -> list[str]:
    """Transcribe audio returning candidate hypotheses across primary and fallback languages concurrently."""
    rec = recognizer or _recognizer
    cfg = get_config()
    primary_lang = cfg.speech_language
    fallback_lang = "en-IN" if primary_lang != "en-IN" else "en-US"
    languages = [primary_lang, fallback_lang]

    def _query(lang: str) -> list[str]:
        try:
            res = rec.recognize_google(audio, language=lang, show_all=True)
            if isinstance(res, dict) and "alternative" in res:
                return [
                    alt["transcript"].strip()
                    for alt in res["alternative"]
                    if isinstance(alt, dict) and alt.get("transcript")
                ]
            elif isinstance(res, str) and res.strip():
                return [res.strip()]
        except Exception:
            pass
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_query, lang) for lang in languages]
        for f in concurrent.futures.as_completed(futures):
            for t in f.result():
                norm = t.lower().strip()
                if norm and norm not in seen:
                    seen.add(norm)
                    candidates.append(t.strip())

    # Fallback to standard recognize_google if show_all didn't return candidates (e.g. in mocked tests)
    if not candidates:
        for lang in languages:
            try:
                res = rec.recognize_google(audio, language=lang)
                if isinstance(res, str) and res.strip():
                    norm = res.lower().strip()
                    if norm not in seen:
                        seen.add(norm)
                        candidates.append(res.strip())
                        break
            except Exception:
                continue

    return candidates


def _transcribe_audio(
    audio: sr.AudioData,
    recognizer: Optional[sr.Recognizer] = None,
) -> Optional[str]:
    """Transcribe audio with fast multi-language parallel retrieval."""
    candidates = _transcribe_audio_candidates(audio, recognizer=recognizer)
    return candidates[0] if candidates else None


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
