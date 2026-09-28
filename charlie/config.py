"""Configuration loader for Charlie.

Loads settings from YAML files and environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
ENV_PATH = PROJECT_ROOT / ".env"

# Load environment variables from .env
load_dotenv(dotenv_path=ENV_PATH)


class Config(BaseModel):
    """Runtime configuration for Charlie."""

    speak_responses: bool = True
    volume_step: int = Field(default=10, ge=1, le=100)
    brightness_step: int = Field(default=10, ge=1, le=100)
    default_browser: Optional[str] = None
    voice_listen_seconds: int = Field(default=8, ge=1, le=60)
    use_llm_fallback: bool = True
    anthropic_api_key: Optional[str] = None
    charlie_model: str = "claude-sonnet-5"
    sites: Dict[str, str] = Field(default_factory=dict)


_config_instance: Optional[Config] = None


def load_config() -> Config:
    """Read YAML configs and environment variables to create a Config instance."""
    settings_data: Dict[str, Any] = {}
    settings_file = CONFIG_DIR / "settings.yaml"
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    settings_data = content
        except Exception:
            settings_data = {}

    sites_data: Dict[str, str] = {}
    sites_file = CONFIG_DIR / "sites.yaml"
    if sites_file.is_file():
        try:
            with open(sites_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    sites_data = {str(k).lower(): str(v) for k, v in content.items()}
        except Exception:
            sites_data = {}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("CHARLIE_MODEL", "claude-sonnet-5")

    return Config(
        speak_responses=settings_data.get("speak_responses", True),
        volume_step=int(settings_data.get("volume_step", 10)),
        brightness_step=int(settings_data.get("brightness_step", 10)),
        default_browser=settings_data.get("default_browser"),
        voice_listen_seconds=int(settings_data.get("voice_listen_seconds", 8)),
        use_llm_fallback=settings_data.get("use_llm_fallback", True),
        anthropic_api_key=api_key if api_key and api_key.strip() else None,
        charlie_model=model if model and model.strip() else "claude-sonnet-5",
        sites=sites_data,
    )


def get_config() -> Config:
    """Get the active cached Config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance


def reload_config() -> Config:
    """Reload configuration from disk."""
    global _config_instance
    _config_instance = load_config()
    return _config_instance
