"""Tests for web search URL construction and browser command formatting."""

from unittest.mock import patch
from charlie.actions.web import (
    build_search_url,
    open_browser_command,
    open_url,
    web_search,
)


def test_build_search_url_google_encoding():
    url = build_search_url("iphone 15 case", "google")
    assert url == "https://www.google.com/search?q=iphone+15+case"


def test_build_search_url_amazon():
    url = build_search_url("wireless earbuds", "amazon")
    assert url == "https://www.amazon.in/s?k=wireless+earbuds"


def test_build_search_url_flipkart():
    url = build_search_url("running shoes", "flipkart")
    assert url == "https://www.flipkart.com/search?q=running+shoes"


def test_build_search_url_youtube():
    url = build_search_url("jazz piano", "youtube")
    assert url == "https://www.youtube.com/results?search_query=jazz+piano"


def test_build_search_url_special_characters():
    url = build_search_url("shoes & socks / shirts", "google")
    assert "shoes+%26+socks+%2F+shirts" in url


def test_build_search_url_unknown_site_fallback():
    # Unknown site defaults to google
    url = build_search_url("quantum computing", "nonexistent_site_123")
    assert "google.com/search?q=quantum+computing" in url


def test_open_browser_command_default():
    cmd = open_browser_command("https://example.com", None)
    assert cmd == ["open", "https://example.com"]


def test_open_browser_command_with_chrome_alias():
    cmd = open_browser_command("https://example.com", "chrome")
    assert cmd == ["open", "-a", "Google Chrome", "https://example.com"]


def test_open_browser_command_with_safari():
    cmd = open_browser_command("https://example.com", "safari")
    assert cmd == ["open", "-a", "Safari", "https://example.com"]


@patch("subprocess.run")
def test_web_search_executes(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stderr = ""

    success, msg = web_search("mechanical keyboards", "amazon", "chrome")
    assert success is True
    assert "Amazon" in msg
    mock_run.assert_called_once_with(
        ["open", "-a", "Google Chrome", "https://www.amazon.in/s?k=mechanical+keyboards"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("subprocess.run")
def test_open_url_adds_https(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stderr = ""

    success, msg = open_url(url="github.com")
    assert success is True
    assert "GitHub" in msg
    mock_run.assert_called_once_with(
        ["open", "https://github.com"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_get_website_display_name():
    from charlie.actions.web import get_website_display_name

    assert get_website_display_name(site="youtube") == "YouTube"
    assert get_website_display_name(site="amazon") == "Amazon"
    assert get_website_display_name(url="github.com") == "GitHub"
    assert get_website_display_name(url="https://www.reddit.com/r/python") == "Reddit"
    assert get_website_display_name(url="https://netflix.com") == "Netflix"
    assert get_website_display_name(url="https://mail.google.com") == "Gmail"
