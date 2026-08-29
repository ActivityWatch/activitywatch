"""
Configuration loader and argument parser for aw-watcher-categorize.
"""

import argparse
import os
from typing import Any, Dict

import tomlkit
from aw_core.config import load_config_toml

default_config = """
[aw-watcher-categorize]
poll_time = 5.0
enable_heuristics = true
auto_update_classes = false
min_confidence_to_learn = 0.85

# AI Provider Settings
# Options: "openai_compatible", "ollama", "gemini", "anthropic", "offline"
ai_provider = "openai_compatible"
ai_api_key = ""
ai_base_url = "https://api.openai.com/v1"
ai_model = "gpt-4o-mini"
""".strip()


def load_config() -> Dict[str, Any]:
    config_dict = load_config_toml("aw-watcher-categorize", default_config)
    return config_dict.get("aw-watcher-categorize", {})


def parse_args():
    config = load_config()

    default_poll_time = float(config.get("poll_time", 5.0))
    default_enable_heuristics = bool(config.get("enable_heuristics", True))
    default_auto_update_classes = bool(config.get("auto_update_classes", False))
    default_ai_provider = str(config.get("ai_provider", "openai_compatible"))
    default_ai_api_key = str(config.get("ai_api_key", ""))
    default_ai_base_url = str(config.get("ai_base_url", "https://api.openai.com/v1"))
    default_ai_model = str(config.get("ai_model", "gpt-4o-mini"))

    parser = argparse.ArgumentParser(
        description="Automated AI-powered categorization watcher and rule learner for ActivityWatch."
    )
    parser.add_argument("--host", dest="host", help="ActivityWatch server host")
    parser.add_argument("--port", dest="port", help="ActivityWatch server port")
    parser.add_argument("--testing", dest="testing", action="store_true", help="Use testing server")
    parser.add_argument("--verbose", dest="verbose", action="store_true", help="Enable verbose/debug logging")
    parser.add_argument(
        "--poll-time",
        dest="poll_time",
        type=float,
        default=default_poll_time,
        help=f"Polling interval in seconds (default: {default_poll_time})",
    )

    # AI Configuration
    parser.add_argument(
        "--ai-provider",
        dest="ai_provider",
        default=default_ai_provider,
        choices=["openai", "openai_compatible", "ollama", "gemini", "anthropic", "offline"],
        help=f"AI model provider (default: {default_ai_provider})",
    )
    parser.add_argument(
        "--ai-api-key",
        dest="ai_api_key",
        default=default_ai_api_key,
        help="API key for AI provider (can also be set via OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--ai-base-url",
        dest="ai_base_url",
        default=default_ai_base_url,
        help=f"API Base URL for OpenAI/Ollama (default: {default_ai_base_url})",
    )
    parser.add_argument(
        "--ai-model",
        dest="ai_model",
        default=default_ai_model,
        help=f"Model name to use (default: {default_ai_model})",
    )

    # Heuristics & Auto-update
    parser.add_argument(
        "--no-heuristics",
        dest="enable_heuristics",
        action="store_false",
        default=default_enable_heuristics,
        help="Disable built-in offline heuristics catalog",
    )
    parser.add_argument(
        "--auto-update",
        dest="auto_update_classes",
        action="store_true",
        default=default_auto_update_classes,
        help="Automatically push new AI-learned rules to aw-server 'classes' setting",
    )

    # Batch Learning Mode
    parser.add_argument(
        "--learn",
        dest="learn",
        action="store_true",
        help="Run batch categorization and rule learning on past uncategorized events, then exit",
    )
    parser.add_argument(
        "--learn-days",
        dest="learn_days",
        type=int,
        default=7,
        help="Number of days of history to inspect when running in --learn mode (default: 7)",
    )
    parser.add_argument(
        "--apply",
        dest="apply_learned_rules",
        action="store_true",
        help="When used with --learn, automatically apply and save generated rules to aw-server",
    )

    return parser.parse_args()
