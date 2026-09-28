"""Live internet tools for Charlie.

Provides real-time weather information and web search snippets to ground
assistant responses in live, up-to-date facts.
"""

from __future__ import annotations

import logging
import re
import ssl
import urllib.parse
import urllib.request
from typing import Optional

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CONTEXT = ssl.create_default_context()

logger = logging.getLogger(__name__)

# Weather query regex
_WEATHER_LOCATION_RE = re.compile(
    r"(?:weather|temperature|forecast|climate|temp)\s+(?:in|for|at|of)\s+([a-zA-Z\s]+)",
    re.IGNORECASE,
)
_WEATHER_GENERAL_RE = re.compile(
    r"\b(?:weather|temperature|forecast|temp|degrees\s+outside|is\s+it\s+raining)\b",
    re.IGNORECASE,
)

# Search trigger keywords
_SEARCH_TRIGGERS = [
    r"\b(?:cost|price|rate)\s+of\b",
    r"\b(?:who\s+won|score\s+of|match\s+between)\b",
    r"\b(?:latest|recent|current)\s+(?:news|update|events?|status)\b",
    r"\b(?:release\s+date|when\s+is\s+the\s+next)\b",
    r"\b(?:stock\s+price|net\s+worth)\b",
]
_SEARCH_TRIGGER_RE = re.compile("|".join(_SEARCH_TRIGGERS), re.IGNORECASE)


def extract_weather_location(text: str) -> Optional[str]:
    """Extract location name from a weather query if specified."""
    m = _WEATHER_LOCATION_RE.search(text)
    if m:
        loc = m.group(1).strip()
        # Clean trailing punctuation or filler
        loc = re.sub(r"[?!.,]+$", "", loc).strip()
        # Remove common trailing phrases like 'today', 'now', 'right now'
        loc = re.sub(r"\b(?:today|now|right\s+now|currently|tomorrow)\b", "", loc, flags=re.IGNORECASE).strip()
        if loc:
            return loc
    return None


def get_live_weather(location: Optional[str] = None) -> Optional[str]:
    """Fetch live weather and temperature via wttr.in.

    Returns concise string e.g. "Delhi: Smoky haze, +24°C" or None on failure.
    """
    try:
        if location and location.strip():
            quoted = urllib.parse.quote(location.strip())
            url = f"https://wttr.in/{quoted}?format=%l:+%C,+%t"
        else:
            url = "https://wttr.in/?format=%l:+%C,+%t"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "curl/7.68.0"},
        )
        with urllib.request.urlopen(req, timeout=3.0, context=_SSL_CONTEXT) as resp:
            data = resp.read().decode("utf-8").strip()
            # If wttr.in returns html error or 404 text
            if data and not data.startswith("<") and "unknown location" not in data.lower():
                return data
    except Exception as err:
        logger.debug("Failed to fetch live weather: %s", err)
    return None


def search_web_snippets(query: str, max_results: int = 2) -> Optional[str]:
    """Fetch concise web search snippets using DuckDuckGo.

    Returns concatenated snippets or None on failure.
    """
    try:
        from ddgs import DDGS
        with DDGS(timeout=3.0) as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if results:
                snippets = []
                for r in results:
                    title = r.get("title", "").strip()
                    body = r.get("body", "").strip()
                    if body:
                        snippets.append(f"{title}: {body}" if title else body)
                if snippets:
                    return "\n".join(snippets[:max_results])
    except Exception as err:
        logger.debug("Failed to fetch web search snippets: %s", err)
    return None


def fetch_live_context(user_text: str) -> Optional[str]:
    """Analyze query and fetch relevant live internet information if needed."""
    # 1. Weather / Temperature check
    if _WEATHER_GENERAL_RE.search(user_text):
        loc = extract_weather_location(user_text)
        weather_info = get_live_weather(loc)
        if weather_info:
            return f"Current Live Weather: {weather_info}"

    # 2. Real-time web search check
    if _SEARCH_TRIGGER_RE.search(user_text):
        snippets = search_web_snippets(user_text)
        if snippets:
            return f"Live Web Search Information:\n{snippets}"

    return None
