"""Pydantic schemas and validators for Charlie actions.

Strict whitelist validation ensures only safe, supported actions are executed.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel, Field, ValidationError, model_validator


class OpenAppParams(BaseModel):
    """Parameters for open_app action."""
    app: str = Field(min_length=1)


class CloseAppParams(BaseModel):
    """Parameters for close_app action."""
    app: str = Field(min_length=1)


class WebSearchParams(BaseModel):
    """Parameters for web_search action."""
    site: str = Field(default="google")
    query: str = Field(min_length=1)
    browser: Optional[str] = None


class OpenUrlParams(BaseModel):
    """Parameters for open_url action."""
    url: Optional[str] = None
    site: Optional[str] = None
    browser: Optional[str] = None

    @model_validator(mode="after")
    def check_url_or_site(self) -> OpenUrlParams:
        if not self.url and not self.site:
            raise ValueError("Either 'url' or 'site' must be specified.")
        return self


class VolumeChangeParams(BaseModel):
    """Parameters for volume_change action."""
    direction: Literal["up", "down"]
    amount: int = Field(default=10, ge=1, le=100)


class VolumeSetParams(BaseModel):
    """Parameters for volume_set action."""
    level: int = Field(ge=0, le=100)


class MuteParams(BaseModel):
    """Parameters for mute action."""
    pass


class UnmuteParams(BaseModel):
    """Parameters for unmute action."""
    pass


class BrightnessChangeParams(BaseModel):
    """Parameters for brightness_change action."""
    direction: Literal["up", "down"]
    amount: int = Field(default=10, ge=1, le=100)


class BrightnessSetParams(BaseModel):
    """Parameters for brightness_set action."""
    level: int = Field(ge=0, le=100)


class MediaControlParams(BaseModel):
    """Parameters for media_control action."""
    command: Literal["play_pause", "next", "previous"]


class UnknownParams(BaseModel):
    """Parameters for unknown action."""
    reason: str = Field(default="Command could not be understood.")


# Whitelist mapping of allowed action names to parameter schemas
PARAM_MODELS: Dict[str, type[BaseModel]] = {
    "open_app": OpenAppParams,
    "close_app": CloseAppParams,
    "web_search": WebSearchParams,
    "open_url": OpenUrlParams,
    "volume_change": VolumeChangeParams,
    "volume_set": VolumeSetParams,
    "mute": MuteParams,
    "unmute": UnmuteParams,
    "brightness_change": BrightnessChangeParams,
    "brightness_set": BrightnessSetParams,
    "media_control": MediaControlParams,
    "unknown": UnknownParams,
}

ALLOWED_ACTIONS = frozenset(PARAM_MODELS.keys())


class Action(BaseModel):
    """Structured representation of an action to be executed."""
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


def make_unknown(reason: str = "Command could not be understood.") -> Action:
    """Create a standardized unknown Action."""
    return Action(action="unknown", params={"reason": reason}, confidence=0.0)


def validate_action(raw: Union[Dict[str, Any], Action]) -> Action:
    """Validate any raw dictionary or Action object against the strict whitelist.

    If validation fails or action is not whitelisted, falls back gracefully to 'unknown'.
    """
    if isinstance(raw, Action):
        raw_dict = raw.model_dump()
    elif isinstance(raw, dict):
        raw_dict = raw
    else:
        return make_unknown(f"Invalid action payload type: {type(raw).__name__}")

    action_name = raw_dict.get("action")
    if not isinstance(action_name, str) or action_name not in ALLOWED_ACTIONS:
        return make_unknown(f"Action '{action_name}' is not in the whitelist.")

    params = raw_dict.get("params", {})
    if not isinstance(params, dict):
        return make_unknown("Action params must be a dictionary.")

    confidence = raw_dict.get("confidence", 1.0)
    try:
        confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = 0.0

    param_model = PARAM_MODELS[action_name]
    try:
        validated_params = param_model.model_validate(params)
        return Action(
            action=action_name,
            params=validated_params.model_dump(),
            confidence=confidence,
        )
    except ValidationError as err:
        errors = "; ".join(e["msg"] for e in err.errors())
        return make_unknown(f"Invalid parameters for '{action_name}': {errors}")
