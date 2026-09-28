"""Optional LLM parser for Charlie using Anthropic Messages API.

Used strictly as a fallback when rule-based parsing yields unknown or low confidence.
The LLM only classifies the command into the fixed action whitelist and never produces
executable shell code.
"""

from __future__ import annotations

import json
import re
from typing import Optional
from charlie.config import get_config
from charlie.schema import Action, make_unknown, validate_action

SYSTEM_PROMPT = """You are Charlie, an intelligent command parser for macOS.
Convert the user's natural language command into one of the following whitelisted actions.
Reply with a single JSON object ONLY. Do not include markdown formatting or commentary.

Allowed Actions and Parameters:
1. open_app: {"app": "App Name"}
2. close_app: {"app": "App Name"}
3. web_search: {"site": "google|amazon|flipkart|youtube|myntra|meesho", "query": "search query", "browser": null or "Chrome|Safari"}
4. open_url: {"url": "https://..." or null, "site": "site_name" or null, "browser": null or "name"}
5. volume_change: {"direction": "up"|"down", "amount": 5|10|25}
6. volume_set: {"level": 0-100}
7. mute: {}
8. unmute: {}
9. brightness_change: {"direction": "up"|"down", "amount": 5|10|25}
10. brightness_set: {"level": 0-100}
11. media_control: {"command": "play_pause"|"next"|"previous"}
12. unknown: {"reason": "explanation"}

Output JSON Schema:
{
  "action": "<action_name>",
  "params": { ... },
  "confidence": <float 0.0-1.0>
}
"""


def parse_llm(text: str) -> Action:
    """Parse text using Anthropic Claude Messages API with strict JSON validation."""
    cfg = get_config()
    if not cfg.anthropic_api_key:
        return make_unknown("LLM parser skipped: ANTHROPIC_API_KEY is not configured.")

    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=cfg.anthropic_api_key,
            timeout=8.0,
        )

        response = client.messages.create(
            model=cfg.charlie_model,
            max_tokens=256,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )

        content = response.content[0].text.strip()
        # Strip potential markdown fences
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"\s*```$", "", content, flags=re.MULTILINE).strip()

        raw_json = json.loads(content)
        return validate_action(raw_json)
    except Exception as err:
        return make_unknown(f"LLM fallback error: {str(err)}")
