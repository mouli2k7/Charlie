"""Unit tests for Charlie internet tools (weather and web search)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from charlie.brain.internet import (
    extract_weather_location,
    fetch_live_context,
    get_live_weather,
    search_web_snippets,
)


class TestInternetTools(unittest.TestCase):
    """Test suite for weather and search tools."""

    def test_extract_weather_location(self) -> None:
        self.assertEqual(extract_weather_location("what is the current temperature in Delhi"), "Delhi")
        self.assertEqual(extract_weather_location("what's the weather in London today"), "London")
        self.assertEqual(extract_weather_location("temperature in San Francisco right now"), "San Francisco")
        self.assertEqual(extract_weather_location("temperature for Tokyo"), "Tokyo")
        self.assertIsNone(extract_weather_location("what's the time right now"))

    @patch("urllib.request.urlopen")
    def test_get_live_weather_mocked(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"Delhi: Smoky haze, +24\xc2\xb0C"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = get_live_weather("Delhi")
        self.assertEqual(result, "Delhi: Smoky haze, +24°C")

    @patch("ddgs.DDGS")
    def test_search_web_snippets_mocked(self, mock_ddgs_cls: MagicMock) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs_instance
        mock_ddgs_instance.text.return_value = [
            {"title": "Test Title 1", "body": "First snippet content."},
            {"title": "Test Title 2", "body": "Second snippet content."},
        ]

        snippets = search_web_snippets("test query", max_results=2)
        self.assertIsNotNone(snippets)
        self.assertIn("First snippet content", snippets)
        self.assertIn("Second snippet content", snippets)

    @patch("charlie.brain.internet.get_live_weather")
    def test_fetch_live_context_weather(self, mock_weather: MagicMock) -> None:
        mock_weather.return_value = "Delhi: Smoky haze, +24°C"
        ctx = fetch_live_context("what is the temperature in Delhi")
        self.assertIsNotNone(ctx)
        self.assertIn("Delhi: Smoky haze, +24°C", ctx)

    @patch("charlie.brain.internet.search_web_snippets")
    def test_fetch_live_context_search(self, mock_search: MagicMock) -> None:
        mock_search.return_value = "iPhone 16 starts at $799."
        ctx = fetch_live_context("what is the cost of iPhone 16")
        self.assertIsNotNone(ctx)
        self.assertIn("iPhone 16 starts at $799", ctx)


if __name__ == "__main__":
    unittest.main()
