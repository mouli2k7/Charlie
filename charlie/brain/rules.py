"""Rule-based natural language parser for Charlie.

Converts natural English text into structured Action objects using regex
and keyword matching. Runs completely offline and fast.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple
from charlie.config import get_config
from charlie.schema import Action, make_unknown, validate_action

# Common filler words and prefixes to strip from user speech/text
FILLER_PATTERNS = [
    r"^(?:hey\s+)?charlie[,\s:]*",
    r"^(?:ok|okay)\s+charlie[,\s:]*",
    r"^hi\s+charlie[,\s:]*",
    r"^please\s+",
    r"^can\s+you\s+(?:please\s+)?",
    r"^could\s+you\s+(?:please\s+)?",
    r"^would\s+you\s+(?:please\s+)?",
    r"^will\s+you\s+(?:please\s+)?",
    r"^kindly\s+",
    r"^go\s+ahead\s+and\s+",
    r"^i\s+want\s+you\s+to\s+",
    r"^help\s+me\s+",
    r"^just\s+",
]

KNOWN_WEB_SITES = {
    "google",
    "amazon",
    "flipkart",
    "youtube",
    "myntra",
    "meesho",
    "reddit",
    "github",
    "wikipedia",
    "bing",
    "yahoo",
    "twitter",
    "linkedin",
    "netflix",
}

BROWSER_FLAGS = [
    (r"\b(?:in|using|with|on)\s+chrome\b", "chrome"),
    (r"\b(?:in|using|with|on)\s+safari\b", "safari"),
    (r"\b(?:in|using|with|on)\s+firefox\b", "firefox"),
    (r"\b(?:in|using|with|on)\s+brave\b", "brave"),
    (r"\b(?:in|using|with|on)\s+edge\b", "edge"),
    (r"\b(?:in|using|with|on)\s+arc\b", "arc"),
]


def clean_input(text: str) -> str:
    """Normalize input text by lowercasing, stripping whitespace and filler phrases."""
    cleaned = text.strip().lower()
    # Strip punctuation at start or end
    cleaned = re.sub(r"^[\s,.:;!?\"']+|[\s,.:;!?\"']+$", "", cleaned)

    # Iteratively strip leading filler phrases
    changed = True
    while changed:
        changed = False
        for pat in FILLER_PATTERNS:
            sub = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            if sub != cleaned:
                cleaned = sub
                changed = True

    # Strip any trailing please/thanks
    cleaned = re.sub(r"\s+(?:please|thanks|thank\s+you)$", "", cleaned).strip()
    return cleaned


def extract_browser(text: str) -> Tuple[str, Optional[str]]:
    """Extract browser modifier if present and return remaining text."""
    browser: Optional[str] = None
    remaining = text
    for pat, b_name in BROWSER_FLAGS:
        if re.search(pat, remaining):
            browser = b_name
            remaining = re.sub(pat, "", remaining).strip()
            break
    return remaining, browser


def parse_volume(text: str) -> Optional[Action]:
    """Parse volume adjustment, volume setting, mute and unmute commands."""
    cfg = get_config()
    default_step = cfg.volume_step

    # Mute
    if re.fullmatch(r"(?:mute|mute\s+the\s+volume|mute\s+audio|silence|be\s+quiet|shut\s+up)", text):
        return Action(action="mute", params={}, confidence=0.99)

    # Unmute
    if re.fullmatch(r"(?:unmute|unmute\s+the\s+volume|unmute\s+audio|restore\s+volume|turn\s+sound\s+back\s+on)", text):
        return Action(action="unmute", params={}, confidence=0.99)

    # Exact volume set: "set volume to 40", "volume 70 percent", "set sound to 30", "volume 50"
    m_set = re.search(
        r"(?:(?:set|turn|change)\s+(?:the\s+)?(?:volume|sound|audio)\s+(?:to\s+)?(\d+)|"
        r"(?:volume|sound)\s+(?:to\s+)?(\d+)(?:\s*(?:%|percent))?|"
        r"(\d+)\s*(?:%|percent)\s+volume)",
        text,
    )
    if m_set:
        level_str = next(g for g in m_set.groups() if g is not None)
        try:
            level = int(level_str)
            if 0 <= level <= 100:
                return Action(action="volume_set", params={"level": level}, confidence=0.95)
        except ValueError:
            pass

    # Step volume change: "volume up", "turn it down a bit", "make it louder", "turn volume up a lot"
    is_up = bool(re.search(r"\b(?:up|louder|increase|raise|higher|more)\b", text))
    is_down = bool(re.search(r"\b(?:down|quieter|softer|decrease|lower|diminish|less)\b", text))

    if (is_up or is_down) and any(kw in text for kw in ["volume", "sound", "audio", "it", "music"]):
        # Determine step size
        step = default_step
        if re.search(r"\b(?:a\s+bit|a\s+little|slightly|tad|notch)\b", text):
            step = 5
        elif re.search(r"\b(?:a\s+lot|much|way)\b", text):
            step = 25
        else:
            m_amt = re.search(r"\bby\s+(\d+)\b", text)
            if m_amt:
                try:
                    step = int(m_amt.group(1))
                except ValueError:
                    pass

        direction = "up" if is_up else "down"
        return Action(
            action="volume_change",
            params={"direction": direction, "amount": step},
            confidence=0.95,
        )

    # Simple "volume up" / "volume down" / "louder" / "softer"
    if text in ("volume up", "turn it up", "louder"):
        return Action(action="volume_change", params={"direction": "up", "amount": default_step}, confidence=0.98)
    if text in ("volume down", "turn it down", "softer", "quieter"):
        return Action(action="volume_change", params={"direction": "down", "amount": default_step}, confidence=0.98)

    return None


def parse_brightness(text: str) -> Optional[Action]:
    """Parse screen brightness adjustment and setting commands."""
    cfg = get_config()
    default_step = cfg.brightness_step

    # Exact brightness set: "set brightness to 50", "brightness 80 percent"
    m_set = re.search(
        r"(?:(?:set|turn|change)\s+(?:the\s+)?(?:screen\s+)?brightness\s+(?:to\s+)?(\d+)|"
        r"(?:screen\s+)?brightness\s+(?:to\s+)?(\d+)(?:\s*(?:%|percent))?|"
        r"(\d+)\s*(?:%|percent)\s+brightness)",
        text,
    )
    if m_set:
        level_str = next(g for g in m_set.groups() if g is not None)
        try:
            level = int(level_str)
            if 0 <= level <= 100:
                return Action(action="brightness_set", params={"level": level}, confidence=0.95)
        except ValueError:
            pass

    # Step brightness change: "brightness up", "dim the screen", "make the screen dimmer", "increase brightness"
    is_up = bool(re.search(r"\b(?:up|increase|raise|higher|brighter|more\s+bright)\b", text))
    is_down = bool(re.search(r"\b(?:down|decrease|lower|dim|dimmer|less\s+bright|darker)\b", text))

    if (is_up or is_down) and any(kw in text for kw in ["brightness", "screen", "display", "it"]):
        step = default_step
        if re.search(r"\b(?:a\s+bit|a\s+little|slightly)\b", text):
            step = 5
        elif re.search(r"\b(?:a\s+lot|much|way)\b", text):
            step = 25
        else:
            m_amt = re.search(r"\bby\s+(\d+)\b", text)
            if m_amt:
                try:
                    step = int(m_amt.group(1))
                except ValueError:
                    pass

        direction = "up" if is_up else "down"
        return Action(
            action="brightness_change",
            params={"direction": direction, "amount": step},
            confidence=0.95,
        )

    return None


def parse_media(text: str) -> Optional[Action]:
    """Parse media playback controls (play, pause, next track, previous track)."""
    # Play / Pause
    if re.fullmatch(r"(?:play|pause|resume|play/pause|toggle\s+playback|play\s+pause)", text):
        return Action(action="media_control", params={"command": "play_pause"}, confidence=0.99)
    if re.fullmatch(r"(?:pause\s+the\s+music|pause\s+music|pause\s+song|pause\s+playback|play\s+music|resume\s+music|resume\s+playback)", text):
        return Action(action="media_control", params={"command": "play_pause"}, confidence=0.98)

    # Next track
    if re.fullmatch(r"(?:next|next\s+song|next\s+track|skip|skip\s+song|skip\s+track|play\s+next\s+song)", text):
        return Action(action="media_control", params={"command": "next"}, confidence=0.99)

    # Previous track
    if re.fullmatch(r"(?:previous|previous\s+song|previous\s+track|prev\s+song|prev\s+track|last\s+song|go\s+back\s+a\s+track|play\s+previous\s+song)", text):
        return Action(action="media_control", params={"command": "previous"}, confidence=0.99)

    return None


def parse_web_search(text: str) -> Optional[Action]:
    """Parse web search queries targeting specific sites or default Google."""
    text_clean, browser = extract_browser(text)

    # 1. "open <site> and search for <query>"
    m1 = re.match(
        r"^open\s+([a-z0-9_-]+)\s+and\s+(?:search\s+(?:for\s+)?|find\s+|look\s+up\s+)(.+)$",
        text_clean,
    )
    if m1:
        site, query = m1.group(1), m1.group(2).strip()
        return Action(
            action="web_search",
            params={"site": site, "query": query, "browser": browser},
            confidence=0.95,
        )

    # 2. "search for <query> on <site>" or "search <query> on <site>" or "find <query> on <site>"
    m2 = re.match(
        r"^(?:search\s+(?:for\s+)?|find\s+|look\s+up\s+)(.+?)\s+on\s+([a-z0-9_-]+)$",
        text_clean,
    )
    if m2:
        query, site = m2.group(1).strip(), m2.group(2).strip()
        return Action(
            action="web_search",
            params={"site": site, "query": query, "browser": browser},
            confidence=0.95,
        )

    # 3. "search on <site> for <query>"
    m3 = re.match(
        r"^search\s+on\s+([a-z0-9_-]+)\s+for\s+(.+)$",
        text_clean,
    )
    if m3:
        site, query = m3.group(1).strip(), m3.group(2).strip()
        return Action(
            action="web_search",
            params={"site": site, "query": query, "browser": browser},
            confidence=0.95,
        )

    # 4. "google <query>"
    m4 = re.match(r"^google\s+(.+)$", text_clean)
    if m4:
        query = m4.group(1).strip()
        return Action(
            action="web_search",
            params={"site": "google", "query": query, "browser": browser},
            confidence=0.95,
        )

    # 5. Generic "search for <query>" or "search <query>"
    m5 = re.match(r"^search\s+(?:for\s+)?(.+)$", text_clean)
    if m5:
        query = m5.group(1).strip()
        return Action(
            action="web_search",
            params={"site": "google", "query": query, "browser": browser},
            confidence=0.90,
        )

    return None


def parse_url(text: str) -> Optional[Action]:
    """Parse direct URL opening or site homepage requests."""
    text_clean, browser = extract_browser(text)

    # "go to <url_or_site>"
    m_goto = re.match(r"^go\s+to\s+(.+)$", text_clean)
    if m_goto:
        target = m_goto.group(1).strip()
        if "." in target or target.startswith("http"):
            return Action(action="open_url", params={"url": target, "browser": browser}, confidence=0.95)
        return Action(action="open_url", params={"site": target, "browser": browser}, confidence=0.95)

    # "open <url>" (e.g. "open github.com", "open https://apple.com", "open youtube")
    m_open = re.match(r"^open\s+(.+)$", text_clean)
    if m_open:
        target = m_open.group(1).strip()
        # Direct URL or domain
        if "." in target or target.startswith("http"):
            return Action(action="open_url", params={"url": target, "browser": browser}, confidence=0.95)
        # Known website homepage (like youtube, reddit, wikipedia)
        if target.lower() in KNOWN_WEB_SITES:
            return Action(action="open_url", params={"site": target.lower(), "browser": browser}, confidence=0.95)

    return None


def parse_apps(text: str) -> Optional[Action]:
    """Parse opening and closing application requests."""
    # Close / Quit app
    m_close = re.match(r"^(?:close|quit|exit|kill)\s+(?:the\s+app\s+|application\s+)?(.+)$", text)
    if m_close:
        app_name = m_close.group(1).strip()
        return Action(action="close_app", params={"app": app_name}, confidence=0.95)

    # Open / Launch app
    m_open = re.match(r"^(?:open|launch|start|run)\s+(?:the\s+app\s+|application\s+)?(.+)$", text)
    if m_open:
        app_name = m_open.group(1).strip()
        return Action(action="open_app", params={"app": app_name}, confidence=0.90)

    return None


def parse_time_and_date(text: str) -> Optional[Action]:
    """Parse time and date inquiries for instant, offline assistant responses."""
    from datetime import datetime

    time_match = bool(
        re.search(
            r"\b(?:what\s+(?:is\s+)?(?:the\s+)?time|what\s+time|current\s+time|time\s+now|time\s+is\s+it|tell\s+me\s+(?:the\s+)?time)\b",
            text,
            re.IGNORECASE,
        )
    )
    if time_match and not any(k in text for k in ("search", "google", "find")):
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        return Action(
            action="answer",
            params={"text": f"It is {time_str}."},
            confidence=1.0,
        )

    date_match = bool(
        re.search(
            r"\b(?:what\s+(?:is\s+)?(?:the\s+)?date|today'?s?\s+date|date\s+today|date\s+is\s+it|what\s+day\s+is\s+(?:it|today)|which\s+day\s+is\s+it)\b",
            text,
            re.IGNORECASE,
        )
    )
    if date_match and not any(k in text for k in ("search", "google", "find")):
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        return Action(
            action="answer",
            params={"text": f"Today is {date_str}."},
            confidence=1.0,
        )

    return None


def parse_conversational(text: str) -> Optional[Action]:
    """Parse common identity and conversational pleasantries for instant offline responses."""
    # Identity: "who are you", "what is your name", "what are you"
    if re.search(r"\b(?:who\s+are\s+you|what\s+(?:is|'s)\s+your\s+name|what\s+are\s+you)\b", text, re.IGNORECASE):
        return Action(
            action="answer",
            params={"text": "I am Charlie, your macOS personal assistant."},
            confidence=1.0,
        )

    # How are you: "how are you", "how are you doing", "how's it going"
    if re.search(r"\b(?:how\s+are\s+you|how\s+are\s+you\s+doing|how'?s\s+it\s+going)\b", text, re.IGNORECASE):
        return Action(
            action="answer",
            params={"text": "I'm doing great and ready to help you!"},
            confidence=1.0,
        )

    # Simple greetings: "hello", "hi", "hey"
    if re.fullmatch(r"(?:hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening)", text, re.IGNORECASE):
        return Action(
            action="answer",
            params={"text": "Hello! How can I help you today?"},
            confidence=1.0,
        )

    # Gratitude: "thank you", "thanks"
    if re.fullmatch(r"(?:thank\s+you|thanks|thank\s+you\s+so\s+much)", text, re.IGNORECASE):
        return Action(
            action="answer",
            params={"text": "You're welcome!"},
            confidence=1.0,
        )

    return None


def parse_weather(text: str) -> Optional[Action]:
    """Parse weather and temperature inquiries for instant live responses."""
    from charlie.brain.internet import extract_weather_location, get_live_weather, _WEATHER_GENERAL_RE

    if not _WEATHER_GENERAL_RE.search(text):
        return None

    # Do not hijack explicit search commands like "search weather on google"
    if any(k in text for k in ("search", "google", "find")):
        return None

    loc = extract_weather_location(text)
    data = get_live_weather(loc)
    if data:
        if ":" in data:
            place, cond = data.split(":", 1)
            place = place.strip()
            cond = cond.strip()
            cond = re.sub(r"\+(\d+)", r"\1", cond)
            if re.match(r"^[\d.,\s-]+$", place):
                text_ans = f"It is currently {cond}."
            else:
                text_ans = f"In {place}, it is currently {cond}."
        else:
            clean = re.sub(r"\+(\d+)", r"\1", data.strip())
            text_ans = f"The current weather is {clean}."

        return Action(
            action="answer",
            params={"text": text_ans},
            confidence=0.98,
        )
    return None


def parse_rules(text: str) -> Action:
    """Evaluate text through rule-based parser and return a validated Action."""
    if not text or not text.strip():
        return make_unknown("Empty input.")

    cleaned = clean_input(text)
    if not cleaned:
        return make_unknown("No command detected.")

    # 0. Time & Date (Instant offline answer)
    action = parse_time_and_date(cleaned)
    if action:
        return validate_action(action)

    # 0.1 Conversational Pleasantries (Instant offline answer)
    action = parse_conversational(cleaned)
    if action:
        return validate_action(action)

    # 0.2 Live Weather & Temperature (Instant live answer)
    action = parse_weather(cleaned)
    if action:
        return validate_action(action)

    # 1. Volume & Mute
    action = parse_volume(cleaned)
    if action:
        return validate_action(action)

    # 2. Brightness
    action = parse_brightness(cleaned)
    if action:
        return validate_action(action)

    # 3. Media Controls
    action = parse_media(cleaned)
    if action:
        return validate_action(action)

    # 4. Web Search
    action = parse_web_search(cleaned)
    if action:
        return validate_action(action)

    # 5. Open URL
    action = parse_url(cleaned)
    if action:
        return validate_action(action)

    # 6. Open / Close App
    action = parse_apps(cleaned)
    if action:
        return validate_action(action)

    # 7. Unmatched -> Unknown
    return make_unknown(f"I didn't understand '{text.strip()}'.")
