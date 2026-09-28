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
    falls back to the Anthropic LLM parser when configured.
    """
    action = parse_rules(text)
    if action.action != "unknown" and action.confidence >= 0.7:
        return action

    cfg = get_config()
    if cfg.use_llm_fallback and cfg.anthropic_api_key:
        llm_action = parse_llm(text)
        if llm_action.action != "unknown":
            return llm_action

    return action
