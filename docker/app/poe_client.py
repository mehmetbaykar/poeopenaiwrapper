"""
Client for interacting with the Poe API.
"""

import logging
import re
import traceback
from typing import AsyncGenerator, List, Literal, Optional, Tuple, cast
import urllib.parse
import os
import mimetypes
import aiofiles

import fastapi_poe as fp
from fastapi import UploadFile

from .config import AVAILABLE_MODELS, POE_API_KEY, REASONING_MODELS
from .exceptions import AuthenticationError, ModelValidationError, PoeAPIError, FileUploadError
from .models import ChatMessage
from .file_handler import FileManager


logger = logging.getLogger(__name__)


class LocalUploadFile:
    """A wrapper for local files to mimic FastAPI's UploadFile for validation."""
    def __init__(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"No such file or directory: '{path}'")
        self.path = path
        self.filename = os.path.basename(path)
        self.size = os.path.getsize(path)
        content_type, _ = mimetypes.guess_type(path)
        self.content_type = content_type or "application/octet-stream"
        self._file = None

    async def read(self) -> bytes:
        async with aiofiles.open(self.path, "rb") as f:
            return await f.read()

    def close(self):
        if self._file and not self._file.closed:
            self._file.close()

class PoeClient:
    """A client for interacting with the Poe API."""

    def __init__(self):
        """Initializes the Poe client."""
        if not POE_API_KEY:
            raise ValueError("POE_API_KEY is required.")
        self.api_key = POE_API_KEY

    @staticmethod
    def is_reasoning_model(model: str) -> bool:
        """Checks if a model is a reasoning model."""
        return model.lower() in [m.lower() for m in REASONING_MODELS]

    @staticmethod
    def estimate_reasoning_tokens(text: str) -> int:
        """Estimates the number of reasoning tokens in a response."""
        if not text:
            return 0

        # Constants for reasoning token estimation
        tokens_per_second = 75
        tokens_per_thinking_occurrence = 40
        chars_per_token = 4

        reasoning_patterns = [
            r"<(?:thinking|think|reasoning)>(.*?)</(?:thinking|think|reasoning)>",
            r"\*Thinking\.\.\.\*\s*\n\n>(.*?)(?=\n\n[^>]|$)",
            r"(?:Let me (?:think|analyze)|I need to consider|My reasoning|"
            r"Step-by-step).*?(?=\n\n|$)",
        ]

        reasoning_content = ""
        for pattern in reasoning_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            reasoning_content += " ".join(matches)

        thinking_count = text.count("Thinking...")
        if thinking_count > 0:
            time_matches = re.findall(r"\((\d+)s elapsed\)", text)
            if time_matches:
                max_time = max(int(t) for t in time_matches)
                return max_time * tokens_per_second

            reasoning_content += " " * (thinking_count * tokens_per_thinking_occurrence)

        return max(len(reasoning_content) // chars_per_token, 0)

    @staticmethod
    def remove_thinking_noise(raw_response: str) -> str:
        """Removes thinking noise from a raw response."""
        if not raw_response or "Thinking..." not in raw_response:
            return raw_response

        clean_response = re.sub(
            r"(?<!^\*)\bThinking\.\.\.(?:\s*\([0-9]+s elapsed\))?\s*",
            "",
            raw_response,
        )
        clean_response = re.sub(r"\s{3,}", " ", clean_response)
        clean_response = re.sub(r"\n{3,}", "\n\n", clean_response).strip()

        if clean_response:
            return f"*Thinking...*\n\n{clean_response}"

        return "*Thinking...*\n\nI'm thinking about your request."

    @staticmethod
    def validate_model(model: str) -> str:
        """Validates that a model is available."""
        if model not in AVAILABLE_MODELS:
            raise ModelValidationError(model, AVAILABLE_MODELS)
        return model

    @staticmethod
    def _extract_text_content(content) -> str:
        """Extracts text content from a message."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        text_parts.append(item["text"])
                    elif "text" in item:
                        text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        return str(content) if content else ""

    @staticmethod
    async def _extract_and_upload_attachments(
        text_content: str,
    ) -> Tuple[str, List[fp.Attachment]]:
        """Extracts file URIs, uploads them, and returns cleaned text and attachments."""
        attachments = []
        # Corrected regex to not include the trailing bracket
        file_pattern = r"\[.*?\]\((file://.*?)\)|(file://[^\s\)]+)"
        
        mutable_content = text_content
        
        matches = list(re.finditer(file_pattern, text_content))

        for match in reversed(matches):
            uri = match.group(1) or match.group(2)
            if not uri:
                continue

            local_file = None
            try:
                parsed_uri = urllib.parse.urlparse(uri)
                file_path = urllib.parse.unquote(parsed_uri.path)

                local_file = LocalUploadFile(file_path)
                
                attachment = await FileManager.upload_file_to_poe(local_file)
                attachments.append(attachment)
                
                # Replace the URI with an empty string
                start, end = match.span()
                mutable_content = mutable_content[:start] + mutable_content[end:]

            except FileNotFoundError:
                logger.warning("File not found at path: %s", file_path)
                continue
            except Exception as e:
                logger.error("Failed to process file URI %s: %s", uri, e)
            finally:
                if local_file:
                    local_file.close()
        
        return mutable_content.strip(), list(reversed(attachments))

    @staticmethod
    async def convert_to_poe_messages(
        messages: List[ChatMessage], attachments: Optional[List[fp.Attachment]] = None
    ) -> List[fp.ProtocolMessage]:
        """Converts a list of chat messages to a list of Poe protocol messages."""
        if not messages:
            raise PoeAPIError("At least one message is required.", 400)

        poe_messages = []
        all_attachments = list(attachments) if attachments else []

        for msg in messages:
            role_mapping = {"assistant": "bot", "user": "user", "system": "system"}
            poe_role = role_mapping.get(msg.role, "user")

            text_content = PoeClient._extract_text_content(msg.content)
            
            cleaned_content, new_attachments = await PoeClient._extract_and_upload_attachments(text_content)
            if new_attachments:
                all_attachments.extend(new_attachments)
                text_content = cleaned_content

            valid_role = cast(Literal["system", "user", "bot"], poe_role)

            poe_message = fp.ProtocolMessage(
                role=valid_role,
                content=text_content or "",
                attachments=[],
            )
            poe_messages.append(poe_message)

        if poe_messages and all_attachments:
            last_user_message_index = -1
            for i in range(len(poe_messages) - 1, -1, -1):
                if poe_messages[i].role == "user":
                    last_user_message_index = i
                    break
            
            if last_user_message_index != -1:
                poe_messages[last_user_message_index].attachments.extend(all_attachments)
            else:
                poe_messages[-1].attachments.extend(all_attachments)

        return poe_messages

    async def get_streaming_response(
        self, messages: List[fp.ProtocolMessage], model: str
    ) -> AsyncGenerator[fp.PartialResponse, None]:
        """Gets a streaming response from the Poe API."""
        try:
            logger.info("Starting streaming response for model %s", model)
            logger.debug("Messages being sent to POE: %s", messages)
            async for partial in fp.get_bot_response(
                messages=messages, bot_name=model, api_key=self.api_key
            ):
                logger.debug("Received partial response: %s", partial)
                yield partial
        except Exception as e:
            logger.error("Error streaming from Poe model %s: %s", model, e)
            logger.error("Error type: %s", type(e).__name__)
            logger.error("Full traceback: %s", traceback.format_exc())

            error_msg = str(e).lower()
            if "unauthorized" in error_msg or "invalid api key" in error_msg:
                raise AuthenticationError(
                    f"POE API authentication failed for model '{model}'."
                ) from e
            if "not found" in error_msg or "unknown model" in error_msg:
                raise PoeAPIError(
                    f"Model '{model}' not found in POE. Available models: {AVAILABLE_MODELS}",
                    404,
                ) from e
            raise PoeAPIError(f"Error communicating with Poe: {e}", 502) from e

    async def get_complete_response(
        self, messages: List[fp.ProtocolMessage], model: str
    ) -> Tuple[str, int]:
        """Gets a complete response from the Poe API."""
        complete_response = ""
        try:
            logger.info("Getting complete response for model %s", model)
            async for partial in self.get_streaming_response(messages, model):
                if hasattr(partial, "text") and partial.text:
                    complete_response += partial.text

            logger.info(
                "Received complete response of %d characters", len(complete_response)
            )

            if self.is_reasoning_model(model):
                if "Thinking..." in complete_response and not complete_response.startswith(
                    "*Thinking...*"
                ):
                    clean_response = self.remove_thinking_noise(complete_response)
                    reasoning_tokens = self.estimate_reasoning_tokens(complete_response)
                    logger.info(
                        "Reasoning model response cleaned: %d chars, ~%d reasoning tokens",
                        len(clean_response),
                        reasoning_tokens,
                    )
                    return clean_response, reasoning_tokens

                reasoning_tokens = self.estimate_reasoning_tokens(complete_response)
                logger.info(
                    "Reasoning model response: %d chars, ~%d reasoning tokens",
                    len(complete_response),
                    reasoning_tokens,
                )
                return complete_response, reasoning_tokens

            return complete_response, 0

        except PoeAPIError:
            raise
        except Exception as e:
            logger.error("Error getting complete response from Poe model %s: %s", model, e)
            raise PoeAPIError(f"Error communicating with Poe: {e}", 502) from e
