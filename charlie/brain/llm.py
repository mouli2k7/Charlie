"""LLM parser for Charlie using Gemini API (with optional Anthropic fallback).

Used strictly as a fallback when rule-based parsing yields unknown or low confidence.
The LLM classifies commands into whitelist actions, or uses the 'answer' action
to provide direct conversational answers, facts, prices, and knowledge.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, Optional

from charlie.config import get_config
from charlie.schema import Action, make_unknown, validate_action

logger = logging.getLogger(__name__)


_gemini_client: Optional[Any] = None
_cached_gemini_key: Optional[str] = None


def _get_gemini_client(api_key: str) -> Any:
    """Return a cached Gemini Client singleton with 1-attempt retry options to prevent hangs."""
    global _gemini_client, _cached_gemini_key
    from google import genai
    from google.genai import types

    if _gemini_client is not None and _cached_gemini_key == api_key:
        return _gemini_client

    http_opts = types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    _gemini_client = genai.Client(api_key=api_key, http_options=http_opts)
    _cached_gemini_key = api_key
    return _gemini_client


def get_system_prompt() -> str:
    """Generate system prompt dynamically populated with current local time."""
    now_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p").lstrip("0")
    return f"""You are Charlie, an intelligent macOS assistant and personal companion with real-time internet search capability.
Current local macOS system time: {now_str}.
Always answer user questions directly and naturally. Never say that you do not have internet access or live data; use any live internet context provided or your internal knowledge.

Your job is to convert user commands or questions into structured JSON actions matching our whitelist.
You must reply with ONLY a single JSON object. Do not include markdown code fences, commentary, or text outside the JSON.

Allowed Whitelist Actions and Parameters:
1. open_app: {{"app": "Exact or Common Application Name"}}
   Example: "launch terminal" -> {{"action": "open_app", "params": {{"app": "Terminal"}}, "confidence": 0.95}}

2. close_app: {{"app": "Application Name to quit"}}
   Example: "quit chrome" -> {{"action": "close_app", "params": {{"app": "Google Chrome"}}, "confidence": 0.95}}

3. web_search: {{"site": "google"|"amazon"|"flipkart"|"youtube"|"myntra"|"meesho", "query": "search query", "browser": null or "Chrome"|"Safari"}}
   Use when the user explicitly asks to search the web or open a browser search.
   Example: "search mechanical keyboard on amazon" -> {{"action": "web_search", "params": {{"site": "amazon", "query": "mechanical keyboard", "browser": null}}, "confidence": 0.95}}

4. open_url: {{"url": "https://..." or null, "site": "site_name" or null, "browser": null}}
   Example: "pull up youtube for me" -> {{"action": "open_url", "params": {{"url": "https://www.youtube.com", "site": "youtube", "browser": null}}, "confidence": 0.95}}

5. volume_change: {{"direction": "up"|"down", "amount": 5|10|25}}
   Note: "a bit" / "a little" = 5; "a lot" = 25; default = 10.
   Example: "make it a bit louder" -> {{"action": "volume_change", "params": {{"direction": "up", "amount": 5}}, "confidence": 0.95}}

6. volume_set: {{"level": 0-100}}
   Example: "set sound to 40 percent" -> {{"action": "volume_set", "params": {{"level": 40}}, "confidence": 0.95}}

7. mute: {{}}
   Example: "silence mac" -> {{"action": "mute", "params": {{}}, "confidence": 0.95}}

8. unmute: {{}}
   Example: "turn sound back on" -> {{"action": "unmute", "params": {{}}, "confidence": 0.95}}

9. brightness_change: {{"direction": "up"|"down", "amount": 5|10|25}}
   Example: "dim the screen please" -> {{"action": "brightness_change", "params": {{"direction": "down", "amount": 10}}, "confidence": 0.95}}

10. brightness_set: {{"level": 0-100}}
    Example: "set display to 75%" -> {{"action": "brightness_set", "params": {{"level": 75}}, "confidence": 0.95}}

11. media_control: {{"command": "play_pause"|"next"|"previous"}}
    Example: "skip to the next track" -> {{"action": "media_control", "params": {{"command": "next"}}, "confidence": 0.95}}

12. answer: {{"text": "Concise, natural answer (1-2 sentences suitable for text-to-speech)"}}
    Use this whenever the user asks any question, asks for prices/costs, facts, explanations, time, date, weather info, math, or conversational chat.
    Example: "what is the cost of iPhone 16" -> {{"action": "answer", "params": {{"text": "The iPhone 16 starts at $799, while the iPhone 16 Pro starts at $999."}}, "confidence": 0.98}}
    Example: "who is the CEO of Google" -> {{"action": "answer", "params": {{"text": "Sundar Pichai is the CEO of Google and Alphabet."}}, "confidence": 0.98}}
    Example: "tell me a joke" -> {{"action": "answer", "params": {{"text": "Why do programmers prefer dark mode? Because light attracts bugs!"}}, "confidence": 0.98}}

13. unknown: {{"reason": "Explanation"}}
    Only use this if the command is completely incomprehensible gibberish.

JSON Output Schema:
{{
  "action": "<action_name>",
  "params": {{ ... }},
  "confidence": <float between 0.0 and 1.0>
}}
"""


def _clean_json_text(text: str) -> str:
    """Clean markdown code blocks and excess whitespace from model output."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace >= first_brace:
        cleaned = cleaned[first_brace : last_brace + 1]
    return cleaned


def _parse_with_gemini(text: str, api_key: str, model_name: str) -> Action:
    """Call Google Gemini API using the google-genai SDK with automatic fast model failover."""
    from google.genai import types
    from charlie.brain.internet import fetch_live_context

    client = _get_gemini_client(api_key)
    prompt = get_system_prompt()
    config = types.GenerateContentConfig(
        system_instruction=prompt,
        response_mime_type="application/json",
        temperature=0.0,
        max_output_tokens=150,
    )

    # Check for live internet context (weather, real-time facts, prices)
    live_ctx = fetch_live_context(text)
    user_payload = text
    if live_ctx:
        user_payload = (
            f"{text}\n\n"
            f"[Live Internet Context retrieved just now]:\n"
            f"{live_ctx}\n"
            f"Use this live information to provide an accurate, up-to-date answer."
        )

    candidate_models = [
        model_name,
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    ]
    seen = set()
    models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

    last_error: Optional[Exception] = None

    for m in models_to_try:
        try:
            chat = client.chats.create(model=m, config=config)
            response = chat.send_message(user_payload)
            content = response.text or ""
            clean_json = _clean_json_text(content)
            raw_data = json.loads(clean_json)
            return validate_action(raw_data)
        except Exception as e:
            last_error = e
            logger.warning("Gemini model %s failed, trying fallback: %s", m, e)
            continue

    return make_unknown(f"Gemini error: {last_error}")


def _parse_with_anthropic(text: str, api_key: str, model_name: str) -> Action:
    """Call Anthropic Claude Messages API."""
    import anthropic

    client = anthropic.Anthropic(
        api_key=api_key,
        timeout=8.0,
    )
    prompt = get_system_prompt()
    response = client.messages.create(
        model=model_name,
        max_tokens=256,
        temperature=0.0,
        system=prompt,
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

    provider = cfg.llm_provider.lower()
    has_gemini = bool(cfg.gemini_api_key)
    has_anthropic = bool(cfg.anthropic_api_key)

    if not has_gemini and not has_anthropic:
        return make_unknown("LLM parser skipped: No API key configured in .env.")

    try:
        if (provider == "gemini" and has_gemini) or (has_gemini and not has_anthropic):
            model = cfg.charlie_model if "gemini" in cfg.charlie_model.lower() else "gemini-3.1-flash-lite"
            return _parse_with_gemini(text, cfg.gemini_api_key, model)  # type: ignore[arg-type]
        elif has_anthropic:
            model = cfg.charlie_model if "claude" in cfg.charlie_model.lower() else "claude-sonnet-5"
            return _parse_with_anthropic(text, cfg.anthropic_api_key, model)  # type: ignore[arg-type]
        else:
            return make_unknown(f"Configured LLM provider '{provider}' has no valid API key.")
    except Exception as err:
        logger.warning("LLM parsing error: %s", err)
        return make_unknown(f"LLM fallback error: {str(err)}")
