"""Module."""
# pylint: disable=import-error
import os
import logging
from typing import Any, Dict, List

MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    # OpenAI
    "gpt-4o": {"client_name": "openai-gpt-4o", "poe_name": "gpt-4o", "reasoning": False},
    "gpt-4.1": {"client_name": "openai-gpt-4.1", "poe_name": "gpt-4.1", "reasoning": False},
    "gpt-4.1-nano": {"client_name": "openai-gpt-4.1-nano", "poe_name": "gpt-4.1-nano", "reasoning": False},
    "gpt-4.1-mini": {"client_name": "openai-gpt-4.1-mini", "poe_name": "gpt-4.1-mini", "reasoning": False},
    "o3-mini-high": {"client_name": "openai-o3-mini-high", "poe_name": "o3-mini-high", "reasoning": True},
    "o3": {"client_name": "openai-o3", "poe_name": "o3", "reasoning": True},
    "o3-pro": {"client_name": "openai-o3-pro", "poe_name": "o3-pro", "reasoning": True},
    "o4-mini": {"client_name": "openai-o4-mini", "poe_name": "o4-mini", "reasoning": True},

    # Anthropic
    "claude-3.7-sonnet": {"client_name": "anthropic-claude-3.7-sonnet", "poe_name": "claude-3.7-sonnet", "reasoning": False},
    "claude-3.7-sonnet-reasoning": {"client_name": "anthropic-claude-3.7-sonnet-reasoning", "poe_name": "claude-3.7-sonnet-reasoning", "reasoning": True},
    "claude-3.7-sonnet-search": {"client_name": "anthropic-claude-3.7-sonnet-search", "poe_name": "claude-3.7-sonnet-search", "reasoning": False},
    "claude-opus-4": {"client_name": "anthropic-claude-opus-4", "poe_name": "claude-opus-4", "reasoning": False},
    "claude-sonnet-4": {"client_name": "anthropic-claude-sonnet-4", "poe_name": "claude-sonnet-4", "reasoning": False},
    "claude-opus-4-reasoning": {"client_name": "anthropic-claude-opus-4-reasoning", "poe_name": "claude-opus-4-reasoning", "reasoning": True},
    "claude-sonnet-4-reasoning": {"client_name": "anthropic-claude-sonnet-4-reasoning", "poe_name": "claude-sonnet-4-reasoning", "reasoning": True},

    # Google
    "gemini-2.5-pro-preview": {"client_name": "google-gemini-2.5-pro-preview", "poe_name": "gemini-2.5-pro-preview", "reasoning": True},
    "gemini-2.5-flash-preview": {"client_name": "google-gemini-2.5-flash-preview", "poe_name": "gemini-2.5-flash-preview", "reasoning": False},
    "gemini-2.0": {"client_name": "google-gemini-2.0", "poe_name": "gemini-2.0", "reasoning": False},

    # Meta
    "llama-4-maverick": {"client_name": "meta-llama-4-maverick", "poe_name": "llama-4-maverick", "reasoning": True},

    # DeepSeek - keep unchanged as requested
    "deepseek-r1": {"client_name": "deepseek-r1", "poe_name": "deepseek-r1", "reasoning": True},

    # xAi
    "grok-3-mini": {"client_name": "xai-grok-3-mini", "poe_name": "grok-3-mini", "reasoning": True},
    "grok-3": {"client_name": "xai-grok-3", "poe_name": "grok-3", "reasoning": True},

    # Perplexity - keep unchanged as requested
    "perplexity-sonar-reasoning": {"client_name": "perplexity-sonar-reasoning", "poe_name": "perplexity-sonar-reasoning", "reasoning": True},
}

# Helper function
def get_poe_name_for_client(client_name: str) -> str:
    """Get POE model name for a client display name"""
    for poe_name, props in MODEL_CATALOG.items():
        if props.get("client_name") == client_name:
            return props.get("poe_name", poe_name)
    return client_name

AVAILABLE_MODELS: List[str] = list(MODEL_CATALOG.keys())
REASONING_MODELS: List[str] = [m for m, props in MODEL_CATALOG.items() if props.get("reasoning", False)]

POE_API_KEY = os.getenv("POE_API_KEY")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "your-local-api-key")

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ALLOWED_FILE_TYPES = [
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
    "application/json",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp"
]

config_logger = logging.getLogger(__name__)

config_logger.info(f"LOCAL_API_KEY loaded: {LOCAL_API_KEY[:10] if LOCAL_API_KEY else 'None'}...")

if not LOCAL_API_KEY or LOCAL_API_KEY == "your-local-api-key":
    raise ValueError("LOCAL_API_KEY environment variable must be set to a secure value")
