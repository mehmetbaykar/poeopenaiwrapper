"""
Client for interacting with the Poe API.
"""

import base64
import logging
import mimetypes
import os
import re
import tempfile
import traceback
import urllib.parse
from typing import AsyncGenerator, List, Literal, Optional, Tuple, cast

import aiofiles
import fastapi_poe as fp

from .config import AVAILABLE_MODELS, POE_API_KEY, REASONING_MODELS
from .exceptions import AuthenticationError, ModelValidationError, PoeAPIError
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
        """Read file contents asynchronously."""
        async with aiofiles.open(self.path, "rb") as f:
            return await f.read()

    def close(self):
        """Close the file if it's open."""
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
        """Extracts text content from a message, including handling image URLs."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        text_parts.append(item["text"])
                    elif item.get("type") == "image_url" and "image_url" in item:
                        image_url = item["image_url"].get("url", "")
                        if image_url.startswith("data:image"):
                            logger.warning("Base64 image found in content - not yet supported")
                            text_parts.append("[Base64 image - upload not yet implemented]")
                        elif image_url.startswith("file://"):
                            text_parts.append(f"[{image_url}]")
                        else:
                            text_parts.append(f"[Image: {image_url}]")
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

                attachment = await FileManager.upload_local_file_to_poe(file_path)
                attachments.append(attachment)

                start, end = match.span()
                mutable_content = mutable_content[:start] + mutable_content[end:]

            except FileNotFoundError:
                logger.warning("File not found at path: %s", file_path)
                continue
            except (IOError, OSError) as e:
                logger.error("Failed to process file URI %s: %s", uri, e)
            finally:
                if local_file:
                    local_file.close()

        return mutable_content.strip(), list(reversed(attachments))

    @staticmethod
    def _parse_data_url(image_url: str) -> Optional[Tuple[str, bytes]]:
        """Parses a data URL and returns the mime type and image bytes."""
        try:
            header, base64_data = image_url.split(",", 1)
            mime_match = re.match(r"data:(image/\w+);base64", header)
            mime_type = mime_match.group(1) if mime_match else "image/png"
            image_bytes = base64.b64decode(base64_data)
            return mime_type, image_bytes
        except (ValueError, TypeError, IndexError) as e:
            logger.error("Failed to parse data URL: %s", e)
            return None

    @staticmethod
    async def _upload_image_bytes(image_bytes: bytes, mime_type: str) -> Optional[fp.Attachment]:
        """Uploads image bytes to Poe and returns an attachment."""
        extension = mime_type.split("/")[-1]
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f".{extension}"
            ) as temp_file:
                temp_file.write(image_bytes)
                temp_path = temp_file.name

            try:
                attachment = await FileManager.upload_local_file_to_poe(temp_path)
                logger.info("Successfully uploaded base64 image as attachment")
                return attachment
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except (IOError, OSError) as e:
            logger.error("Failed to write or upload temporary image file: %s", e)
        return None

    @staticmethod
    async def _handle_image_item(item: dict) -> Tuple[Optional[str], Optional[fp.Attachment]]:
        """Handles a single image item from the message content."""
        image_url = item.get("image_url", {}).get("url", "")

        if image_url.startswith("data:image"):
            parsed_data = PoeClient._parse_data_url(image_url)
            if parsed_data:
                mime_type, image_bytes = parsed_data
                attachment = await PoeClient._upload_image_bytes(image_bytes, mime_type)
                if attachment:
                    return None, attachment
            return "[Failed to process base64 image]", None

        if image_url.startswith("file://"):
            return f"[{image_url}]", None

        return f"[Image URL: {image_url}]", None

    @staticmethod
    async def _extract_and_upload_base64_images(content) -> Tuple[str, List[fp.Attachment]]:
        """Extracts base64 images from structured content and uploads them to Poe."""
        if not isinstance(content, list):
            return str(content) if content else "", []

        text_parts = []
        attachments = []

        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "text" and "text" in item:
                    text_parts.append(item["text"])
                elif item_type == "image_url" and "image_url" in item:
                    text, attachment = await PoeClient._handle_image_item(item)
                    if text:
                        text_parts.append(text)
                    if attachment:
                        attachments.append(attachment)
                elif "text" in item:
                    text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)

        return "\n".join(text_parts), attachments

    @staticmethod
    async def convert_to_poe_messages(
        messages: List[ChatMessage], attachments: Optional[List[fp.Attachment]] = None
    ) -> List[fp.ProtocolMessage]:
        """Converts chat messages to Poe protocol messages following the official pattern."""
        if not messages:
            raise PoeAPIError("At least one message is required.", 400)

        logger.info("Converting %d messages to Poe format with %d explicit attachments",
                   len(messages), len(attachments) if attachments else 0)

        poe_messages: List[fp.ProtocolMessage] = []
        all_attachments: List[fp.Attachment] = []

        for i, msg in enumerate(messages):
            role_mapping = {"assistant": "bot", "user": "user", "system": "system"}
            poe_role = role_mapping.get(msg.role, "user")

            text_content, base64_attachments = await PoeClient._extract_and_upload_base64_images(
                msg.content
            )

            if base64_attachments:
                logger.info("Found %d base64 images in message %d", len(base64_attachments), i)
                all_attachments.extend(base64_attachments)
            else:
                text_content = PoeClient._extract_text_content(msg.content)

            logger.debug("Message %d (%s): content length=%d", i, msg.role, len(text_content))

            cleaned_content, embedded_attachments = await PoeClient._extract_and_upload_attachments(
                text_content
            )

            if embedded_attachments:
                logger.info("Found %d embedded file URIs in message %d",
                           len(embedded_attachments), i)
                all_attachments.extend(embedded_attachments)
                text_content = cleaned_content

            valid_role = cast(Literal["system", "user", "bot"], poe_role)

            poe_message = fp.ProtocolMessage(
                role=valid_role,
                content=text_content or "",
                attachments=[]
            )

            poe_messages.append(poe_message)

        if attachments:
            logger.info("Adding %d explicit attachments to collection", len(attachments))
            all_attachments.extend(attachments)

        if all_attachments:
            last_user_idx = -1
            for i in range(len(poe_messages) - 1, -1, -1):
                if poe_messages[i].role == "user":
                    last_user_idx = i
                    break

            if last_user_idx != -1:
                poe_messages[last_user_idx].attachments = all_attachments
                logger.info("Added %d attachments to last user message at index %d",
                           len(all_attachments), last_user_idx)
            else:
                poe_messages[-1].attachments = all_attachments
                logger.warning("No user message found, adding attachments to last message")
        else:
            logger.warning("No attachments found to add to messages")

        logger.info("Converted messages successfully, returning %d Poe messages", len(poe_messages))
        return poe_messages

    async def get_streaming_response(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, messages: List[fp.ProtocolMessage], model: str,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[fp.ToolDefinition]] = None
    ) -> AsyncGenerator[fp.PartialResponse, None]:
        """Gets a streaming response from the Poe API."""
        try:
            logger.info("Starting streaming response for model %s", model)
            logger.debug("Messages being sent to POE: %s", messages)

            # When we have tools but no executables (proxy mode), we should use stream_request_base
            # instead of get_bot_response which requires tool_executables
            if tools:
                logger.info("Using native Poe function calling with %d tools", len(tools))
                request = fp.QueryRequest(
                    query=messages,
                    user_id="",
                    conversation_id="",
                    message_id="",
                    version="1.0",
                    type="query"
                )
                async for partial in fp.stream_request(
                    request=request,
                    bot_name=model,
                    api_key=self.api_key
                ):
                    logger.debug("Received partial response: %s", partial)
                    yield partial
            else:
                # No tools, use the simpler get_bot_response
                async for partial in fp.get_bot_response(
                    messages=messages, bot_name=model, api_key=self.api_key,
                    temperature=temperature,
                    stop_sequences=stop_sequences or []
                ):
                    logger.debug("Received partial response: %s", partial)
                    yield partial
        except Exception as e:
            logger.error("Error streaming from Poe model %s: %s", model, e)
            logger.error("Error type: %s", type(e).__name__)
            logger.error("Full traceback: %s", traceback.format_exc())

            error_msg = str(e).lower()
            error_type_name = type(e).__name__

            # Check for specific Poe errors first
            if error_type_name == "InvalidParameterError":
                raise PoeAPIError(
                    f"Invalid parameter: {e}",
                    400,
                    error_type="invalid_request_error"
                ) from e
            if error_type_name == "InsufficientFundError":
                raise PoeAPIError(
                    "Insufficient funds to process this request",
                    402,
                    error_type="insufficient_fund"
                ) from e

            # Then check error message patterns
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

    async def get_complete_response(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, messages: List[fp.ProtocolMessage], model: str,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[fp.ToolDefinition]] = None
    ) -> Tuple[str, int]:
        """Gets a complete response from the Poe API."""
        complete_response = ""
        try:
            logger.info("Getting complete response for model %s", model)
            async for partial in self.get_streaming_response(
                messages, model, temperature, stop_sequences, tools
            ):
                # Handle attachment URLs from image generation bots
                if hasattr(partial, "attachment") and partial.attachment:
                    complete_response += f"\n![Image]({partial.attachment.url})\n"
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
