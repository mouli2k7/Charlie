"""Charlie Brain module.

Coordinates rule-based parsing and optional LLM fallback.
"""

from __future__ import annotations

from charlie.brain.rules import parse_rules
from charlie.brain.llm import parse_llm
from charlie.config import get_config
from charlie.schema import Action


def parse(text: str) -> Action:
    """Parse natural language command into a validated Action.

    Tries fast offline rule-based parser first. If unknown or low confidence,
    falls back to the configured LLM parser (Gemini or Anthropic).
    """
    action = parse_rules(text)

    cfg = get_config()
    has_llm = cfg.use_llm_fallback and (cfg.gemini_api_key or cfg.anthropic_api_key)

    # When LLM is active, if rule parser matched a generic Google web search
    # (e.g. "search exchange rate", "search latest phones", "google USD to INR"),
    # do NOT dump the user into a browser. Route to the LLM to search, analyze, and speak the answer!
    if has_llm and action.action == "web_search" and action.params.get("site") == "google" and not action.params.get("browser"):
        llm_action = parse_llm(text)
        if llm_action.action != "unknown":
            return llm_action

    if action.action != "unknown" and action.confidence >= 0.7:
        return action

    if has_llm:
        llm_action = parse_llm(text)
        if llm_action.action != "unknown":
            return llm_action

    return action
