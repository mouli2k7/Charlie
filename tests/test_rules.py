"""Tests for the rule-based natural language brain parser."""

import pytest
from charlie.brain.rules import parse_rules


@pytest.mark.parametrize(
    "phrase,expected_action,expected_params",
    [
        # --- App Management (open_app, close_app) ---
        ("open safari", "open_app", {"app": "safari"}),
        ("launch notes", "open_app", {"app": "notes"}),
        ("start spotify", "open_app", {"app": "spotify"}),
        ("open vs code", "open_app", {"app": "vs code"}),
        ("please open chrome", "open_app", {"app": "chrome"}),
        ("can you please open terminal", "open_app", {"app": "terminal"}),
        ("hey charlie launch visual studio code", "open_app", {"app": "visual studio code"}),
        ("close chrome", "close_app", {"app": "chrome"}),
        ("quit spotify", "close_app", {"app": "spotify"}),
        ("exit notes", "close_app", {"app": "notes"}),
        ("close safari", "close_app", {"app": "safari"}),
        ("kill slack", "close_app", {"app": "slack"}),

        # --- Web Search ---
        (
            "open amazon and search for wireless earbuds",
            "web_search",
            {"site": "amazon", "query": "wireless earbuds", "browser": None},
        ),
        (
            "search headphones on flipkart",
            "web_search",
            {"site": "flipkart", "query": "headphones", "browser": None},
        ),
        (
            "google best laptops",
            "web_search",
            {"site": "google", "query": "best laptops", "browser": None},
        ),
        (
            "search for running shoes on flipkart",
            "web_search",
            {"site": "flipkart", "query": "running shoes", "browser": None},
        ),
        (
            "search for pizza places near me",
            "web_search",
            {"site": "google", "query": "pizza places near me", "browser": None},
        ),
        (
            "look up macbook on amazon",
            "web_search",
            {"site": "amazon", "query": "macbook", "browser": None},
        ),
        (
            "search python tutorials on youtube",
            "web_search",
            {"site": "youtube", "query": "python tutorials", "browser": None},
        ),
        (
            "find summer dresses on myntra",
            "web_search",
            {"site": "myntra", "query": "summer dresses", "browser": None},
        ),
        (
            "search sarees on meesho",
            "web_search",
            {"site": "meesho", "query": "sarees", "browser": None},
        ),
        (
            "search on google for good coffee",
            "web_search",
            {"site": "google", "query": "good coffee", "browser": None},
        ),
        (
            "google rust programming in chrome",
            "web_search",
            {"site": "google", "query": "rust programming", "browser": "chrome"},
        ),

        # --- Open URL ---
        ("open youtube", "open_url", {"site": "youtube", "url": None, "browser": None}),
        ("go to github.com", "open_url", {"url": "github.com", "site": None, "browser": None}),
        ("open reddit.com", "open_url", {"url": "reddit.com", "site": None, "browser": None}),
        ("go to https://apple.com", "open_url", {"url": "https://apple.com", "site": None, "browser": None}),
        ("open wikipedia", "open_url", {"site": "wikipedia", "url": None, "browser": None}),

        # --- Volume Controls ---
        ("volume up", "volume_change", {"direction": "up", "amount": 10}),
        ("turn it down a bit", "volume_change", {"direction": "down", "amount": 5}),
        ("turn volume up a lot", "volume_change", {"direction": "up", "amount": 25}),
        ("turn it up", "volume_change", {"direction": "up", "amount": 10}),
        ("lower the volume by 15", "volume_change", {"direction": "down", "amount": 15}),
        ("increase volume by 20", "volume_change", {"direction": "up", "amount": 20}),
        ("set volume to 40", "volume_set", {"level": 40}),
        ("volume 70 percent", "volume_set", {"level": 70}),
        ("set volume to 30", "volume_set", {"level": 30}),
        ("set volume to 0", "volume_set", {"level": 0}),
        ("volume 100", "volume_set", {"level": 100}),
        ("mute", "mute", {}),
        ("unmute", "unmute", {}),
        ("mute the volume", "mute", {}),
        ("restore volume", "unmute", {}),

        # --- Brightness Controls ---
        ("brightness up", "brightness_change", {"direction": "up", "amount": 10}),
        ("make the screen dimmer", "brightness_change", {"direction": "down", "amount": 10}),
        ("dim the screen", "brightness_change", {"direction": "down", "amount": 10}),
        ("increase brightness by 20", "brightness_change", {"direction": "up", "amount": 20}),
        ("dim the screen a bit", "brightness_change", {"direction": "down", "amount": 5}),
        ("set brightness to 50", "brightness_set", {"level": 50}),
        ("brightness 80 percent", "brightness_set", {"level": 80}),

        # --- Media Controls ---
        ("play", "media_control", {"command": "play_pause"}),
        ("pause", "media_control", {"command": "play_pause"}),
        ("pause the music", "media_control", {"command": "play_pause"}),
        ("next song", "media_control", {"command": "next"}),
        ("next track", "media_control", {"command": "next"}),
        ("skip song", "media_control", {"command": "next"}),
        ("previous track", "media_control", {"command": "previous"}),
        ("play previous song", "media_control", {"command": "previous"}),

        # --- Time & Date (Instant Offline Answer) ---
        ("what is the time", "answer", None),
        ("what time is it", "answer", None),
        ("what is today date", "answer", None),

        # --- Unknown Phrases ---
        ("tell me a joke", "unknown", None),
        ("what is the weather today", "unknown", None),
        ("asdfghjkl", "unknown", None),
    ],
)
def test_parse_rules_phrases(phrase, expected_action, expected_params):
    action = parse_rules(phrase)
    assert action.action == expected_action
    if expected_params is not None:
        for k, v in expected_params.items():
            assert action.params.get(k) == v
