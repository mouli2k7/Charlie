"""LLM parser for Charlie using Gemini API (with optional Anthropic fallback).

Used strictly as a fallback when rule-based parsing yields unknown or low confidence.
The LLM only classifies the command into the fixed action whitelist and never produces
executable shell code.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from charlie.config import get_config
from charlie.schema import Action, make_unknown, validate_action

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Charlie, an intelligent macOS command assistant.
Your job is to convert natural language commands into structured JSON actions matching our strict whitelist.
You must reply with ONLY a single JSON object. Do not include markdown code fences, commentary, or text outside the JSON.

Allowed Whitelist Actions and Parameters:
1. open_app: {"app": "Exact or Common Application Name"}
   Example: "launch terminal" -> {"action": "open_app", "params": {"app": "Terminal"}, "confidence": 0.95}

2. close_app: {"app": "Application Name to quit"}
   Example: "quit chrome" -> {"action": "close_app", "params": {"app": "Google Chrome"}, "confidence": 0.95}

3. web_search: {"site": "google"|"amazon"|"flipkart"|"youtube"|"myntra"|"meesho", "query": "search query", "browser": null or "Chrome"|"Safari"}
   Example: "search mechanical keyboard on amazon" -> {"action": "web_search", "params": {"site": "amazon", "query": "mechanical keyboard", "browser": null}, "confidence": 0.95}

4. open_url: {"url": "https://..." or null, "site": "site_name" or null, "browser": null}
   Note: For web services/sites (e.g. YouTube, GitHub, Reddit) when the user asks to open or pull them up, use open_url with the full URL.
   Example: "can you pull up youtube for me" -> {"action": "open_url", "params": {"url": "https://www.youtube.com", "site": "youtube", "browser": null}, "confidence": 0.95}

5. volume_change: {"direction": "up"|"down", "amount": 5|10|25}
   Note: "a bit" / "a little" = 5; "a lot" = 25; default = 10.
   Example: "make it a bit louder" -> {"action": "volume_change", "params": {"direction": "up", "amount": 5}, "confidence": 0.95}

6. volume_set: {"level": 0-100}
   Example: "set sound to 40 percent" -> {"action": "volume_set", "params": {"level": 40}, "confidence": 0.95}

7. mute: {}
   Example: "silence mac" -> {"action": "mute", "params": {}, "confidence": 0.95}

8. unmute: {}
   Example: "turn sound back on" -> {"action": "unmute", "params": {}, "confidence": 0.95}

9. brightness_change: {"direction": "up"|"down", "amount": 5|10|25}
   Example: "dim the screen please" -> {"action": "brightness_change", "params": {"direction": "down", "amount": 10}, "confidence": 0.95}

10. brightness_set: {"level": 0-100}
    Example: "set display to 75%" -> {"action": "brightness_set", "params": {"level": 75}, "confidence": 0.95}

11. media_control: {"command": "play_pause"|"next"|"previous"}
    Example: "skip to the next track" -> {"action": "media_control", "params": {"command": "next"}, "confidence": 0.95}

12. unknown: {"reason": "Friendly explanation of why the action is not supported"}
    Example: "what is the capital of France" -> {"action": "unknown", "params": {"reason": "General questions are not supported; Charlie is a Mac controller."}, "confidence": 0.95}

JSON Output Schema:
{
  "action": "<action_name>",
  "params": { ... },
  "confidence": <float between 0.0 and 1.0>
}
"""


def _clean_json_text(text: str) -> str:
    """Clean markdown code blocks and excess whitespace from model output."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    # In case there is text before the first '{' or after the last '}'
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace >= first_brace:
        cleaned = cleaned[first_brace : last_brace + 1]
    return cleaned


def _parse_with_gemini(text: str, api_key: str, model_name: str) -> Action:
    """Call Google Gemini API using the google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        temperature=0.0,
    )

    chat = client.chats.create(model=model_name, config=config)
    response = chat.send_message(text)

    content = response.text or ""
    clean_json = _clean_json_text(content)
    raw_data = json.loads(clean_json)
    return validate_action(raw_data)


def _parse_with_anthropic(text: str, api_key: str, model_name: str) -> Action:
    """Call Anthropic Claude Messages API."""
    import anthropic

    client = anthropic.Anthropic(
        api_key=api_key,
        timeout=8.0,
    )
    response = client.messages.create(
        model=model_name,
        max_tokens=256,
        temperature=0.0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    content = response.content[0].text if response.content else ""
    clean_json = _clean_json_text(content)
    raw_data = json.loads(clean_json)
    return validate_action(raw_data)


def parse_llm(text: str) -> Action:
    """Parse text using configured LLM provider with strict whitelist JSON validation.

    Prefers Gemini when GEMINI_API_KEY is available (or when llm_provider == 'gemini'),
    and falls back to Anthropic when ANTHROPIC_API_KEY is configured.
    Always catches errors and falls back to 'unknown'.
    """
    cfg = get_config()

    if not cfg.use_llm_fallback:
        return make_unknown("LLM fallback is disabled in settings.")

    # Determine provider
    provider = cfg.llm_provider.lower()
    has_gemini = bool(cfg.gemini_api_key)
    has_anthropic = bool(cfg.anthropic_api_key)

    if not has_gemini and not has_anthropic:
        return make_unknown("LLM parser skipped: No API key configured in .env.")

    try:
        if (provider == "gemini" and has_gemini) or (has_gemini and not has_anthropic):
            model = cfg.charlie_model if "gemini" in cfg.charlie_model.lower() else "gemini-3.5-flash-lite"
            return _parse_with_gemini(text, cfg.gemini_api_key, model)  # type: ignore[arg-type]
        elif has_anthropic:
            model = cfg.charlie_model if "claude" in cfg.charlie_model.lower() else "claude-sonnet-5"
            return _parse_with_anthropic(text, cfg.anthropic_api_key, model)  # type: ignore[arg-type]
        else:
            return make_unknown(f"Configured LLM provider '{provider}' has no valid API key.")
    except Exception as err:
        logger.warning("LLM parsing error: %s", err)
        return make_unknown(f"LLM fallback error: {str(err)}")
