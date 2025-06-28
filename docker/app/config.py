import os
from typing import List, Dict, Any

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
    "o3-mini": {"client_name": "openai-o3-mini", "poe_name": "o3-mini", "reasoning": True},
    "o3-deep-research": {"client_name": "openai-o3-deep-research", "poe_name": "o3-deep-research", "reasoning": True},
    "o4-mini-deep-research": {"client_name": "openai-o4-mini-deep-research", "poe_name": "o4-mini-deep-research", "reasoning": True},
    "o1": {"client_name": "openai-o1", "poe_name": "o1", "reasoning": True},
    "o1-mini": {"client_name": "openai-o1-mini", "poe_name": "o1-mini", "reasoning": True},
    "o1-preview": {"client_name": "openai-o1-preview", "poe_name": "o1-preview", "reasoning": True},
    "o1-pro": {"client_name": "openai-o1-pro", "poe_name": "o1-pro", "reasoning": True},
    "gpt-4.5-preview": {"client_name": "openai-gpt-4.5-preview", "poe_name": "gpt-4.5-preview", "reasoning": True},
    "gpt-4o-mini": {"client_name": "openai-gpt-4o-mini", "poe_name": "gpt-4o-mini", "reasoning": False},
    "chatgpt-4o-latest": {"client_name": "openai-chatgpt-4o-latest", "poe_name": "chatgpt-4o-latest", "reasoning": False},
    "gpt-4o-search": {"client_name": "openai-gpt-4o-search", "poe_name": "gpt-4o-search", "reasoning": False},
    "gpt-4o-mini-search": {"client_name": "openai-gpt-4o-mini-search", "poe_name": "gpt-4o-mini-search", "reasoning": False},
    
    # Anthropic
    "claude-3.7-sonnet": {"client_name": "anthropic-claude-3.7-sonnet", "poe_name": "claude-3.7-sonnet", "reasoning": False},
    "claude-3.7-sonnet-reasoning": {"client_name": "anthropic-claude-3.7-sonnet-reasoning", "poe_name": "claude-3.7-sonnet-reasoning", "reasoning": True},
    "claude-3.7-sonnet-search": {"client_name": "anthropic-claude-3.7-sonnet-search", "poe_name": "claude-3.7-sonnet-search", "reasoning": False},
    "claude-opus-4": {"client_name": "anthropic-claude-opus-4", "poe_name": "claude-opus-4", "reasoning": False},
    "claude-sonnet-4": {"client_name": "anthropic-claude-sonnet-4", "poe_name": "claude-sonnet-4", "reasoning": False},
    "claude-opus-4-reasoning": {"client_name": "anthropic-claude-opus-4-reasoning", "poe_name": "claude-opus-4-reasoning", "reasoning": True},
    "claude-sonnet-4-reasoning": {"client_name": "anthropic-claude-sonnet-4-reasoning", "poe_name": "claude-sonnet-4-reasoning", "reasoning": True},
    "claude-sonnet-3.5": {"client_name": "anthropic-claude-sonnet-3.5", "poe_name": "claude-sonnet-3.5", "reasoning": False},
    "claude-haiku-3.5": {"client_name": "anthropic-claude-haiku-3.5", "poe_name": "claude-haiku-3.5", "reasoning": False},
    "claude-opus-4-search": {"client_name": "anthropic-claude-opus-4-search", "poe_name": "claude-opus-4-search", "reasoning": False},
    "claude-sonnet-4-search": {"client_name": "anthropic-claude-sonnet-4-search", "poe_name": "claude-sonnet-4-search", "reasoning": False},
    "claude-sonnet-3.7-search": {"client_name": "anthropic-claude-sonnet-3.7-search", "poe_name": "claude-sonnet-3.7-search", "reasoning": False},
    "claude-sonnet-3.5-search": {"client_name": "anthropic-claude-sonnet-3.5-search", "poe_name": "claude-sonnet-3.5-search", "reasoning": False},
    "claude-haiku-3.5-search": {"client_name": "anthropic-claude-haiku-3.5-search", "poe_name": "claude-haiku-3.5-search", "reasoning": False},
    "claude-opus-3": {"client_name": "anthropic-claude-opus-3", "poe_name": "claude-opus-3", "reasoning": True},
    
    # Google
    "gemini-2.5-pro-preview": {"client_name": "google-gemini-2.5-pro-preview", "poe_name": "gemini-2.5-pro-preview", "reasoning": True},
    "gemini-2.5-flash-preview": {"client_name": "google-gemini-2.5-flash-preview", "poe_name": "gemini-2.5-flash-preview", "reasoning": False},
    "gemini-2.5-pro": {"client_name": "google-gemini-2.5-pro", "poe_name": "gemini-2.5-pro", "reasoning": True},
    "gemini-2.5-flash": {"client_name": "google-gemini-2.5-flash", "poe_name": "gemini-2.5-flash", "reasoning": True},
    "gemini-2.5-flash-lite-preview": {"client_name": "google-gemini-2.5-flash-lite-preview", "poe_name": "gemini-2.5-flash-lite-preview", "reasoning": True},
    "gemini-2.0": {"client_name": "google-gemini-2.0", "poe_name": "gemini-2.0", "reasoning": False},
    "gemini-2.0-flash-preview": {"client_name": "google-gemini-2.0-flash-preview", "poe_name": "gemini-2.0-flash-preview", "reasoning": True},
    "gemini-2.0-flash": {"client_name": "google-gemini-2.0-flash", "poe_name": "gemini-2.0-flash", "reasoning": True},
    "gemini-1.5-pro": {"client_name": "google-gemini-1.5-pro", "poe_name": "gemini-1.5-pro", "reasoning": True},
    
    # Meta
    "llama-4-maverick": {"client_name": "meta-llama-4-maverick", "poe_name": "llama-4-maverick", "reasoning": True},
    "llama-4-scout-b10": {"client_name": "meta-llama-4-scout-b10", "poe_name": "llama-4-scout-b10", "reasoning": True},
    "llama-4-scout-t": {"client_name": "meta-llama-4-scout-t", "poe_name": "llama-4-scout-t", "reasoning": True},
    "llama-4-scout-nitro": {"client_name": "meta-llama-4-scout-nitro", "poe_name": "llama-4-scout-nitro", "reasoning": True},
    "llama-4-scout": {"client_name": "meta-llama-4-scout", "poe_name": "llama-4-scout", "reasoning": True},
    "llama-4-maverick-t": {"client_name": "meta-llama-4-maverick-t", "poe_name": "llama-4-maverick-t", "reasoning": True},
    "llama-3-70b-groq": {"client_name": "meta-llama-3-70b-groq", "poe_name": "llama-3-70b-groq", "reasoning": True},
    "llama-3.3-70b-fw": {"client_name": "meta-llama-3.3-70b-fw", "poe_name": "llama-3.3-70b-fw", "reasoning": True},
    "llama-3.3-70b": {"client_name": "meta-llama-3.3-70b", "poe_name": "llama-3.3-70b", "reasoning": True},
    
    # DeepSeek - keep unchanged as requested
    "deepseek-r1": {"client_name": "deepseek-r1", "poe_name": "deepseek-r1", "reasoning": True},
    "deepseek-r1-fw": {"client_name": "deepseek-r1-fw", "poe_name": "deepseek-r1-fw", "reasoning": True},
    "deepseek-r1-distill": {"client_name": "deepseek-r1-distill", "poe_name": "deepseek-r1-distill", "reasoning": True},
    "deepseek-r1-di": {"client_name": "deepseek-r1-di", "poe_name": "deepseek-r1-di", "reasoning": True},
    "deepseek-r1-turbo-di": {"client_name": "deepseek-r1-turbo-di", "poe_name": "deepseek-r1-turbo-di", "reasoning": True},
    "deepseek-v3": {"client_name": "deepseek-v3", "poe_name": "deepseek-v3", "reasoning": True},
    "deepseek-v3-fw": {"client_name": "deepseek-v3-fw", "poe_name": "deepseek-v3-fw", "reasoning": True},
    
    # xAi
    "grok-3-mini": {"client_name": "xai-grok-3-mini", "poe_name": "grok-3-mini", "reasoning": True},
    "grok-3": {"client_name": "xai-grok-3", "poe_name": "grok-3", "reasoning": True},

    # Perplexity - keep unchanged as requested
    "perplexity-sonar-reasoning": {"client_name": "perplexity-sonar-reasoning", "poe_name": "perplexity-sonar-reasoning", "reasoning": True},
    "perplexity-sonar-rsn": {"client_name": "perplexity-sonar-rsn", "poe_name": "perplexity-sonar-rsn", "reasoning": True},
    "perplexity-sonar-rsn-pro": {"client_name": "perplexity-sonar-rsn-pro", "poe_name": "perplexity-sonar-rsn-pro", "reasoning": True},
    "perplexity-deep-research": {"client_name": "perplexity-deep-research", "poe_name": "perplexity-deep-research", "reasoning": True},
    "perplexity-r1-1776": {"client_name": "perplexity-r1-1776", "poe_name": "perplexity-r1-1776", "reasoning": True},
    "perplexity-sonar": {"client_name": "perplexity-sonar", "poe_name": "perplexity-sonar", "reasoning": False},
    "perplexity-sonar-pro": {"client_name": "perplexity-sonar-pro", "poe_name": "perplexity-sonar-pro", "reasoning": False},

    # Qwen
    "qwq-32b-b10": {"client_name": "qwen-qwq-32b-b10", "poe_name": "qwq-32b-b10", "reasoning": True},
    "qwq-32b-t": {"client_name": "qwen-qwq-32b-t", "poe_name": "qwq-32b-t", "reasoning": True},
    "qwq-32b-preview-t": {"client_name": "qwen-qwq-32b-preview-t", "poe_name": "qwq-32b-preview-t", "reasoning": True},
    "qwen-qwq-32b": {"client_name": "qwen-qwq-32b", "poe_name": "qwen-qwq-32b", "reasoning": True},
    "qwen3-235b-a22b-fw": {"client_name": "qwen3-235b-a22b-fw", "poe_name": "qwen3-235b-a22b-fw", "reasoning": True},
    "qwen3-235b-a22b": {"client_name": "qwen3-235b-a22b", "poe_name": "qwen3-235b-a22b", "reasoning": True},
    "qwen3-235b-a22b-di": {"client_name": "qwen3-235b-a22b-di", "poe_name": "qwen3-235b-a22b-di", "reasoning": True},
    "qwen-3-235b-t": {"client_name": "qwen-3-235b-t", "poe_name": "qwen-3-235b-t", "reasoning": True},

    # Mistral
    "mistral-medium": {"client_name": "mistral-medium", "poe_name": "mistral-medium", "reasoning": False},
    "mistral-small-3.1": {"client_name": "mistral-small-3.1", "poe_name": "mistral-small-3.1", "reasoning": True},

    # Inception
    "inception-mercury-coder": {"client_name": "inception-mercury-coder", "poe_name": "inception-mercury-coder", "reasoning": True},

    # Research Tools
    "gpt-researcher": {"client_name": "gpt-researcher", "poe_name": "gpt-researcher", "reasoning": True},

    # MiniMax
    "minimax-m1": {"client_name": "minimax-m1", "poe_name": "minimax-m1", "reasoning": True},

    # Poe Tools
    "assistant": {"client_name": "poe-assistant", "poe_name": "assistant", "reasoning": False},
    "app-creator": {"client_name": "poe-app-creator", "poe_name": "app-creator", "reasoning": False},
    "web-search": {"client_name": "poe-web-search", "poe_name": "web-search", "reasoning": False},
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

import logging
config_logger = logging.getLogger(__name__)

config_logger.info(f"LOCAL_API_KEY loaded: {LOCAL_API_KEY[:10] if LOCAL_API_KEY else 'None'}...")

if not LOCAL_API_KEY or LOCAL_API_KEY == "your-local-api-key":
    raise ValueError("LOCAL_API_KEY environment variable must be set to a secure value")