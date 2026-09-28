"""Tests for voice input module (Phase 2).

Tests are done without actually recording audio by mocking SpeechRecognition
at the library level. This ensures CI safety and reproducibility.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import speech_recognition as sr

from charlie.inputs.voice_input import (
    _strip_wake_prefix,
    listen_and_transcribe,
)


# -------------------------------------------------------------------
# Wake-prefix stripping tests (no mocking needed — pure string logic)
# -------------------------------------------------------------------

def test_strip_hey_charlie():
    assert _strip_wake_prefix("hey charlie open safari") == "open safari"


def test_strip_charlie_prefix():
    assert _strip_wake_prefix("charlie set volume to 30") == "set volume to 30"


def test_strip_ok_charlie():
    assert _strip_wake_prefix("ok charlie mute") == "mute"


def test_no_prefix_unchanged():
    assert _strip_wake_prefix("brightness up") == "brightness up"


def test_strip_with_comma():
    assert _strip_wake_prefix("hey charlie, open notes") == "open notes"


def test_strip_case_insensitive():
    assert _strip_wake_prefix("HEY CHARLIE volume up") == "volume up"


# -------------------------------------------------------------------
# listen_and_transcribe() tests with mocked microphone + recognizer
# -------------------------------------------------------------------

@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_successful_transcription(mock_mic_cls, mock_recognizer):
    """Simulate clean speech recognition returning a valid command."""
    mock_source = MagicMock()
    mock_mic_cls.return_value.__enter__.return_value = mock_source
    mock_recognizer.adjust_for_ambient_noise = MagicMock()
    mock_recognizer.listen.return_value = MagicMock()
    mock_recognizer.recognize_google.return_value = "open safari"

    result = listen_and_transcribe(timeout=5)
    assert result == "open safari"


@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_transcription_strips_hey_charlie(mock_mic_cls, mock_recognizer):
    """Wake phrase is stripped from recognized speech."""
    mock_source = MagicMock()
    mock_mic_cls.return_value.__enter__.return_value = mock_source
    mock_recognizer.adjust_for_ambient_noise = MagicMock()
    mock_recognizer.listen.return_value = MagicMock()
    mock_recognizer.recognize_google.return_value = "hey charlie set volume to 40"

    result = listen_and_transcribe(timeout=5)
    assert result == "set volume to 40"


@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_unknown_value_returns_none(mock_mic_cls, mock_recognizer):
    """When speech is unclear, return None without crashing."""
    mock_source = MagicMock()
    mock_mic_cls.return_value.__enter__.return_value = mock_source
    mock_recognizer.adjust_for_ambient_noise = MagicMock()
    mock_recognizer.listen.return_value = MagicMock()
    mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()

    result = listen_and_transcribe(timeout=5)
    assert result is None


@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_request_error_returns_none(mock_mic_cls, mock_recognizer):
    """Network error from speech service returns None gracefully."""
    mock_source = MagicMock()
    mock_mic_cls.return_value.__enter__.return_value = mock_source
    mock_recognizer.adjust_for_ambient_noise = MagicMock()
    mock_recognizer.listen.return_value = MagicMock()
    mock_recognizer.recognize_google.side_effect = sr.RequestError("service unavailable")

    result = listen_and_transcribe(timeout=5)
    assert result is None


@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_wait_timeout_returns_none(mock_mic_cls, mock_recognizer):
    """If no speech is detected within timeout, return None gracefully."""
    mock_source = MagicMock()
    mock_mic_cls.return_value.__enter__.return_value = mock_source
    mock_recognizer.adjust_for_ambient_noise = MagicMock()
    mock_recognizer.listen.side_effect = sr.WaitTimeoutError()

    result = listen_and_transcribe(timeout=1)
    assert result is None


@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_mic_os_error_returns_none(mock_mic_cls, mock_recognizer):
    """Microphone hardware failure returns None without crashing."""
    mock_mic_cls.return_value.__enter__.side_effect = OSError("No audio device")

    result = listen_and_transcribe(timeout=5)
    assert result is None


# -------------------------------------------------------------------
# Integration: voice result feeds the exact same parse/dispatch pipeline
# -------------------------------------------------------------------

@patch("charlie.inputs.voice_input._recognizer")
@patch("speech_recognition.Microphone")
def test_voice_output_matches_text_output(mock_mic_cls, mock_recognizer):
    """Ensure voice path produces same Action as text path for same phrase."""
    from charlie.brain import parse

    mock_source = MagicMock()
    mock_mic_cls.return_value.__enter__.return_value = mock_source
    mock_recognizer.adjust_for_ambient_noise = MagicMock()
    mock_recognizer.listen.return_value = MagicMock()
    mock_recognizer.recognize_google.return_value = "set volume to 30"

    # Voice path
    voice_text = listen_and_transcribe(timeout=5)
    voice_action = parse(voice_text)

    # Text path
    text_action = parse("set volume to 30")

    assert voice_action.action == text_action.action
    assert voice_action.params == text_action.params
