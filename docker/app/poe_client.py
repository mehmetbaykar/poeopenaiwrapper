"""Module."""
# pylint: disable=import-error
import logging
import re
from typing import AsyncGenerator, List, Literal, Optional, Tuple, cast

import fastapi_poe as fp

from .config import AVAILABLE_MODELS, POE_API_KEY, REASONING_MODELS
from .exceptions import PoeAPIError
from .models import ChatMessage

logger = logging.getLogger(__name__)

class PoeClient:
    def __init__(self):
        if not POE_API_KEY:
            raise ValueError("POE_API_KEY is required")
        self.api_key = POE_API_KEY

    @staticmethod
    def is_reasoning_model(model: str) -> bool:
        """Check if the model is a reasoning model that needs special handling"""
        return model.lower() in [m.lower() for m in REASONING_MODELS]

    @staticmethod
    def estimate_reasoning_tokens(text: str) -> int:
        """Estimate reasoning tokens from response text."""
        if not text:
            return 0

        # Extract all reasoning content with unified patterns
        reasoning_patterns = [
            r'<(?:thinking|think|reasoning)>(.*?)</(?:thinking|think|reasoning)>',  # XML tags
            r'\*Thinking\.\.\.\*\s*\n\n>(.*?)(?=\n\n[^>]|$)',  # Block quotes
            r'(?:Let me (?:think|analyze)|I need to consider|My reasoning|Step-by-step).*?(?=\n\n|$)',  # Explicit reasoning
        ]

        reasoning_content = ""
        for pattern in reasoning_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            reasoning_content += " ".join(matches)

        # Handle O1-style thinking dots
        thinking_count = text.count('Thinking...')
        if thinking_count > 0:
            # Use timing if available, otherwise estimate from count
            time_matches = re.findall(r'\((\d+)s elapsed\)', text)
            if time_matches:
                max_time = max(int(t) for t in time_matches)
                return max_time * 75  # ~75 tokens per second
            else:
                reasoning_content += " " * (thinking_count * 40)  # ~10 tokens per occurrence

        # Convert characters to tokens (roughly 1 token per 4 characters)
        return max(len(reasoning_content) // 4, 0)


    @staticmethod
    def remove_thinking_noise(raw_response: str) -> str:
        """Format OpenAI reasoning models to match normal ai thinking format."""
        if not raw_response or "Thinking..." not in raw_response:
            return raw_response

        # Remove "Thinking..." noise and clean up formatting
        clean_response = re.sub(r'(?<!^\*)\bThinking\.\.\.(?:\s*\([0-9]+s elapsed\))?\s*', '', raw_response)
        clean_response = re.sub(r'\s{3,}', ' ', clean_response)
        clean_response = re.sub(r'\n{3,}', '\n\n', clean_response).strip()

        # Format with Normal AI thinking-style header
        return f"*Thinking...*\n\n{clean_response}" if clean_response else "*Thinking...*\n\nI'm thinking about your request."

    @staticmethod
    def validate_model(model: str) -> str:
        if model not in AVAILABLE_MODELS:
            raise PoeAPIError(
                f"Model '{model}' not available. Available models: {AVAILABLE_MODELS}",
                400
            )
        return model

    @staticmethod
    def _extract_text_content(content) -> str:
        """Extract text content from complex message formats"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text' and 'text' in item:
                        text_parts.append(item['text'])
                    elif 'text' in item:
                        text_parts.append(item['text'])
                elif isinstance(item, str):
                    text_parts.append(item)
            return '\n'.join(text_parts)
        return str(content) if content else ""

    @staticmethod
    def convert_to_poe_messages(messages: List[ChatMessage], attachments: Optional[List[fp.Attachment]] = None) -> List[fp.ProtocolMessage]:
        if not messages:
            raise PoeAPIError("At least one message is required", 400)

        poe_messages = []

        for i, msg in enumerate(messages):
            # Convert role and format content
            role_mapping = {"assistant": "bot", "user": "user", "system": "system"}
            poe_role = role_mapping.get(msg.role, "user")

            text_content = PoeClient._extract_text_content(msg.content)
            content = f"{poe_role.title()}: {text_content}" if poe_role != "user" else f"User: {text_content}"

            # Add attachments only to the last message
            msg_attachments = attachments if i == len(messages) - 1 else None

            # Cast role to valid type
            valid_role = cast(Literal["system", "user", "bot"], poe_role)

            # Create message with or without attachments
            if msg_attachments:
                poe_message = fp.ProtocolMessage(
                    role=valid_role,
                    content=content or "",
                    attachments=msg_attachments
                )
            else:
                poe_message = fp.ProtocolMessage(
                    role=valid_role,
                    content=content or ""
                )
            poe_messages.append(poe_message)

        return poe_messages

    async def get_streaming_response(
        self,
        messages: List[fp.ProtocolMessage],
        model: str
    ) -> AsyncGenerator[fp.PartialResponse, None]:
        try:
            logger.info(f"Starting streaming response for model {model}")
            logger.debug(f"Messages being sent to POE: {messages}")
            async for partial in fp.get_bot_response(
                messages=messages,
                bot_name=model,
                api_key=self.api_key
            ):
                logger.debug(f"Received partial response: {partial}")
                yield partial
        except Exception as e:
            logger.error(f"Error streaming from Poe model {model}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Check for specific error types
            error_msg = str(e).lower()
            if "unauthorized" in error_msg or "invalid api key" in error_msg:
                raise PoeAPIError(f"POE API authentication failed for model '{model}'. Check your POE_API_KEY or model availability.", 401)
            elif "not found" in error_msg or "unknown model" in error_msg:
                raise PoeAPIError(f"Model '{model}' not found in POE. Available models: {AVAILABLE_MODELS}", 404)
            else:
                raise PoeAPIError(f"Error communicating with Poe: {str(e)}", 502)

    async def get_complete_response(
        self,
        messages: List[fp.ProtocolMessage],
        model: str
    ) -> Tuple[str, int]:
        """
        Get complete response from Poe.
        Returns (raw_content, reasoning_tokens_estimate)
        For reasoning models, we forward the raw content and estimate reasoning tokens.
        """
        complete_response = ""
        try:
            logger.info(f"Getting complete response for model {model}")
            async for partial in self.get_streaming_response(messages, model):
                if hasattr(partial, 'text') and partial.text:
                    complete_response += partial.text

            logger.info(f"Received complete response of {len(complete_response)} characters")

            # For reasoning models, process and format the response
            if self.is_reasoning_model(model):
                # Check if response has raw "Thinking..." noise
                if "Thinking..." in complete_response and not complete_response.startswith("*Thinking...*"):
                    # Format the response to match normal ai thinking format
                    clean_response = self.remove_thinking_noise(complete_response)
                    reasoning_tokens = self.estimate_reasoning_tokens(complete_response)
                    logger.info(f"Reasoning model response cleaned: {len(clean_response)} chars, ~{reasoning_tokens} reasoning tokens")
                    return clean_response, reasoning_tokens
                else:
                    # For models already in correct format, return as-is
                    reasoning_tokens = self.estimate_reasoning_tokens(complete_response)
                    logger.info(f"Reasoning model response: {len(complete_response)} chars, ~{reasoning_tokens} reasoning tokens")
                    return complete_response, reasoning_tokens
            else:
                return complete_response, 0

        except PoeAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting complete response from Poe model {model}: {e}")
            raise PoeAPIError(f"Error communicating with Poe: {str(e)}", 502)
