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

# Search trigger keywords for live internet information
_SEARCH_TRIGGERS = [
    r"\b(?:cost|price|rate|pricing)\s+of\b",
    r"\b(?:who\s+won|score\s+of|match\s+between|who\s+is\s+winning)\b",
    r"\b(?:latest|recent|current|new|top|best)\s+(?:phones?|smartphones?|gadgets?|laptops?|models?|news|update|events?|status|movies?)\b",
    r"\b(?:release\s+date|when\s+is\s+the\s+next|launch\s+date)\b",
    r"\b(?:stock\s+price|net\s+worth|market\s+cap|crypto|bitcoin)\b",
    r"\b(?:phones?|smartphones?|iphone|samsung|galaxy|pixel|oneplus|laptops?|macbook)\b",
    r"\b(?:search\s+(?:for|about|on\s+google)?|google|look\s+up|find\s+out)\b",
    r"\b(?:vs|versus|compare|comparison|specs|specifications)\b",
    r"^(?:who|what|when|where|why|how|which)\b",
]
_SEARCH_TRIGGER_RE = re.compile("|".join(_SEARCH_TRIGGERS), re.IGNORECASE)

_FOREX_RE = re.compile(
    r"\b(?:exchange|forex|currency|rates?|dollar|dollars|rupee|rupees|inr|usd|eur|euro|euros|gbp|pound|pounds|cad|aed|yen|jpy)\b",
    re.IGNORECASE,
)


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
        with urllib.request.urlopen(req, timeout=2.5, context=_SSL_CONTEXT) as resp:
            data = resp.read().decode("utf-8").strip()
            if data and not data.startswith("<") and "unknown location" not in data.lower():
                return data
    except Exception as err:
        logger.debug("Failed to fetch live weather: %s", err)
    return None


def get_live_forex(text: str) -> Optional[str]:
    """Fetch real-time live currency exchange rates from open exchange API."""
    if not _FOREX_RE.search(text):
        return None
    try:
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/USD",
            headers={"User-Agent": "Charlie/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2.0, context=_SSL_CONTEXT) as resp:
            import json
            data = json.loads(resp.read().decode())
            rates = data.get("rates", {})
            inr = rates.get("INR")
            eur = rates.get("EUR")
            gbp = rates.get("GBP")
            aed = rates.get("AED")
            cad = rates.get("CAD")
            if inr and eur and gbp:
                return (
                    f"Live Real-Time Forex Rates (USD Base):\n"
                    f"1 USD = {inr:.2f} INR\n"
                    f"1 EUR = {inr/eur:.2f} INR (1 USD = {eur:.2f} EUR)\n"
                    f"1 GBP = {inr/gbp:.2f} INR (1 USD = {gbp:.2f} GBP)\n"
                    f"1 CAD = {inr/cad:.2f} INR\n"
                    f"1 AED = {inr/aed:.2f} INR"
                )
    except Exception as err:
        logger.debug("Failed to fetch live forex rates: %s", err)
    return None


def search_web_snippets(query: str, max_results: int = 2) -> Optional[str]:
    """Fetch concise web search snippets using DuckDuckGo with fast API backends."""
    clean_q = re.sub(
        r"^(?:search\s+(?:for\s+|about\s+|on\s+google\s+(?:for\s+)?)?|google\s+|look\s+up\s+|tell\s+me\s+about\s+)",
        "",
        query.strip(),
        flags=re.IGNORECASE,
    ).strip()
    if not clean_q:
        clean_q = query.strip()

    try:
        from ddgs import DDGS
        for backend in ("api", "lite"):
            try:
                with DDGS(timeout=2.0) as ddgs:
                    results = list(ddgs.text(clean_q, backend=backend, max_results=max_results))
                    if results:
                        snippets = []
                        for r in results:
                            title = r.get("title", "").strip()
                            body = r.get("body", "").strip()
                            if body:
                                snippets.append(f"{title}: {body}" if title else body)
                        if snippets:
                            return "\n".join(snippets[:max_results])
            except Exception:
                continue
    except Exception as err:
        logger.debug("Failed to fetch web search snippets: %s", err)
    return None


def fetch_live_context(user_text: str) -> Optional[str]:
    """Analyze query and fetch relevant live internet information in real-time."""
    # 1. Weather / Temperature check
    if _WEATHER_GENERAL_RE.search(user_text):
        loc = extract_weather_location(user_text)
        weather_info = get_live_weather(loc)
        if weather_info:
            return f"Current Live Weather: {weather_info}"

    # 2. Live Forex / Currency check
    forex_info = get_live_forex(user_text)
    if forex_info:
        return forex_info

    # 3. Real-time web search check (phones, gadgets, news, prices, sports)
    if _SEARCH_TRIGGER_RE.search(user_text):
        snippets = search_web_snippets(user_text, max_results=2)
        if snippets:
            return f"Live Web Search Information:\n{snippets}"

    return None
