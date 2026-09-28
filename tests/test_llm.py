"""Tests for LLM fallback parser (Phase 3).

Covers both mocked SDK calls for deterministic CI and live Gemini API calls
when GEMINI_API_KEY is configured.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from charlie.brain.llm import (
    _clean_json_text,
    _parse_with_gemini,
    parse_llm,
)
from charlie.config import Config, get_config


class TestLLMCleaning(unittest.TestCase):
    """Test JSON cleaning utility."""

    def test_clean_raw_json(self) -> None:
        raw = '{"action": "open_app", "params": {"app": "Notes"}, "confidence": 0.95}'
        self.assertEqual(_clean_json_text(raw), raw)

    def test_clean_markdown_code_fence(self) -> None:
        raw = '```json\n{"action": "open_app", "params": {"app": "Notes"}, "confidence": 0.95}\n```'
        expected = '{"action": "open_app", "params": {"app": "Notes"}, "confidence": 0.95}'
        self.assertEqual(_clean_json_text(raw), expected)

    def test_clean_extra_commentary(self) -> None:
        raw = 'Here is the JSON:\n{"action": "mute", "params": {}, "confidence": 1.0}\nHope that helps!'
        expected = '{"action": "mute", "params": {}, "confidence": 1.0}'
        self.assertEqual(_clean_json_text(raw), expected)


class TestLLMMocked(unittest.TestCase):
    """Test LLM parsing with mocked Gemini client."""

    @patch("google.genai.Client")
    def test_parse_with_gemini_success(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_chat = MagicMock()
        mock_client.chats.create.return_value = mock_chat

        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "action": "open_url",
            "params": {"url": "https://www.youtube.com", "site": "youtube", "browser": None},
            "confidence": 0.95,
        })
        mock_chat.send_message.return_value = mock_resp

        action = _parse_with_gemini("pull up youtube", "dummy_key", "gemini-3.5-flash-lite")
        self.assertEqual(action.action, "open_url")
        self.assertEqual(action.params.get("url"), "https://www.youtube.com")
        self.assertEqual(action.confidence, 0.95)

    @patch("charlie.brain.llm.get_config")
    def test_parse_llm_skipped_when_disabled(self, mock_get_config: MagicMock) -> None:
        mock_get_config.return_value = Config(use_llm_fallback=False)
        action = parse_llm("any prompt")
        self.assertEqual(action.action, "unknown")
        self.assertIn("disabled", action.params.get("reason", ""))

    @patch("charlie.brain.llm.get_config")
    def test_parse_llm_skipped_when_no_key(self, mock_get_config: MagicMock) -> None:
        mock_get_config.return_value = Config(gemini_api_key=None, anthropic_api_key=None)
        action = parse_llm("any prompt")
        self.assertEqual(action.action, "unknown")
        self.assertIn("No API key", action.params.get("reason", ""))

    @patch("google.genai.Client")
    def test_parse_with_gemini_handles_api_exception(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chats.create.side_effect = RuntimeError("API connection failure")

        action = parse_llm("make it louder")
        self.assertEqual(action.action, "unknown")
        self.assertIn("error", action.params.get("reason", "").lower())


class TestLLMLiveGemini(unittest.TestCase):
    """Live Gemini API integration tests (executed when valid GEMINI_API_KEY is present)."""

    def setUp(self) -> None:
        self.cfg = get_config()
        if not self.cfg.gemini_api_key:
            self.skipTest("GEMINI_API_KEY not configured in .env")

    def test_live_pull_up_youtube(self) -> None:
        action = parse_llm("can you pull up youtube for me")
        self.assertIn(action.action, ("open_url", "open_app"))
        self.assertGreater(action.confidence, 0.5)

    def test_live_make_it_a_bit_louder(self) -> None:
        action = parse_llm("make it a bit louder please")
        self.assertEqual(action.action, "volume_change")
        self.assertEqual(action.params.get("direction"), "up")

    def test_live_dim_the_screen(self) -> None:
        action = parse_llm("dim the screen please")
        self.assertEqual(action.action, "brightness_change")
        self.assertEqual(action.params.get("direction"), "down")

    def test_live_assistant_question(self) -> None:
        action = parse_llm("what is the cost of iPhone 16")
        self.assertEqual(action.action, "answer")
        self.assertTrue(len(action.params.get("text", "")) > 0)

    def test_live_unknown_command(self) -> None:
        action = parse_llm("asdfghjklqwerty12345!@#$%^")
        self.assertEqual(action.action, "unknown")


if __name__ == "__main__":
    unittest.main()
