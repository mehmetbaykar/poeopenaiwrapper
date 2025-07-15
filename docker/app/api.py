"""
FastAPI handlers for OpenAI-compatible endpoints.
"""

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from fastapi.responses import StreamingResponse

from .config import MODEL_CATALOG, get_poe_name_for_client
from .exceptions import ModerationError, PoeAPIError, StreamingError
from .models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    CompletionTokensDetails,
    ModelInfo,
    ModelsResponse,
    ModerationCategories,
    ModerationCategoryScores,
    ModerationRequest,
    ModerationResponse,
    ModerationResult,
    PromptTokensDetails,
    Usage,
)
from .native_tool_handler import NativeToolHandler
from .poe_client import PoeClient
from .tool_handler import ToolCallHandler

logger = logging.getLogger(__name__)

# Constants for token estimation (rough approximations)
WORDS_PER_TOKEN = 0.75  # Approximate tokens per word
CHARS_PER_TOKEN = 4  # Approximate characters per token


class APIHandler:
    """Handles the core logic of the API endpoints."""

    def __init__(self):
        """Initializes the API handler with a PoeClient instance."""
        self.poe_client = PoeClient()
        self.tool_handler = ToolCallHandler()
        self.native_tool_handler = NativeToolHandler()

    def get_poe_model_name(self, client_name: str) -> str:
        """Converts a client-facing model name to the internal Poe model name."""
        poe_name = get_poe_name_for_client(client_name)
        logger.debug("Model name mapping: %s -> %s", client_name, poe_name)
        return poe_name

    def _log_request_details(self, request: ChatCompletionRequest) -> None:
        """Logs detailed information about the chat completion request."""
        message_summary = [
            f"{msg.role}({len(str(msg.content)) if msg.content else 0})"
            for msg in request.messages
        ]
        logger.debug("Messages: [%s]", ", ".join(message_summary))

        # Log debug info
        self._log_debug_info(request)

        # Warn about unsupported parameters
        self._warn_unsupported_params(request)

        # Log tools info
        if request.tools:
            self._log_tools_info(request)

    def _log_debug_info(self, request: ChatCompletionRequest) -> None:
        """Log debug information for the request."""
        if request.temperature != 0.0:
            logger.debug("Temperature: %f", request.temperature)
        if request.max_tokens or request.max_completion_tokens:
            logger.debug(
                "Max tokens: %s", request.max_tokens or request.max_completion_tokens
            )
        if request.user:
            logger.debug("User: %s...", request.user[:20])

    def _warn_unsupported_params(self, request: ChatCompletionRequest) -> None:
        """Warn about unsupported parameters."""
        warnings = {
            "n": (request.n and request.n > 1,
                  f"Parameter 'n={request.n}' is not supported by Poe API. "
                  "Only single completions are generated."),
            "presence_penalty": (
                request.presence_penalty,
                "Parameter 'presence_penalty' is not supported by Poe API and will be ignored."
            ),
            "frequency_penalty": (
                request.frequency_penalty,
                "Parameter 'frequency_penalty' is not supported by Poe API and will be ignored."
            ),
            "top_p": (request.top_p,
                      "Parameter 'top_p' is not supported by Poe API and will be ignored."),
            "seed": (request.seed,
                     "Parameter 'seed' is not supported by Poe API and will be ignored."),
            "max_tokens": (request.max_tokens or request.max_completion_tokens,
                           "Parameter 'max_tokens' is simulated via prompts. Results may vary."),
            "response_format": (request.response_format,
                                "Parameter 'response_format' is enforced via prompts. "
                                "Not guaranteed to be valid JSON.")
        }

        for _, (condition, message) in warnings.items():
            if condition:
                logger.warning(message)

    def _log_tools_info(self, request: ChatCompletionRequest) -> None:
        """Log information about tools usage."""
        poe_model = self.get_poe_model_name(request.model)
        if self.native_tool_handler.supports_native_tools(poe_model):
            logger.info("Using native Poe function calling for model %s", poe_model)
        else:
            logger.info(
                "Function calling is implemented via XML prompts for model %s "
                "(native tools not supported)",
                poe_model
            )

    def _calculate_token_usage(self, request: ChatCompletionRequest, complete_text: str) -> dict:
        """Calculates token usage for a chat completion."""
        prompt_tokens = sum(
            int(len(str(msg.content).split()) * WORDS_PER_TOKEN) if msg.content else 0
            for msg in request.messages
        )
        completion_tokens = int(len(complete_text.split()) * WORDS_PER_TOKEN)

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def _create_token_details(self, request: ChatCompletionRequest, reasoning_tokens: int):
        """Creates token details for reasoning models."""
        completion_details = None
        prompt_details = None
        if PoeClient.is_reasoning_model(request.model):
            completion_details = CompletionTokensDetails(
                reasoning_tokens=reasoning_tokens, audio_tokens=None
            )
            prompt_details = PromptTokensDetails(cached_tokens=0, audio_tokens=None)
        return completion_details, prompt_details

    def _get_default_moderation_values(self):
        """Returns default values for moderation categories and scores."""
        default_false = {
            "hate/threatening": False,
            "harassment/threatening": False,
            "self-harm/intent": False,
            "self-harm/instructions": False,
            "sexual/minors": False,
            "violence/graphic": False,
        }
        default_scores = {
            "hate/threatening": 0.01,
            "harassment/threatening": 0.01,
            "self-harm/intent": 0.01,
            "self-harm/instructions": 0.01,
            "sexual/minors": 0.01,
            "violence/graphic": 0.01,
        }
        return default_false, default_scores

    def _create_moderation_prompt(self, text: str) -> str:
        """Creates a moderation prompt for analysis."""
        return (
            f"Analyze this text for harmful content. "
            f"Respond with JSON containing:\n"
            f"- flagged: boolean (true if content is harmful)\n"
            f"- hate: boolean\n"
            f"- harassment: boolean\n"
            f"- self_harm: boolean\n"
            f"- sexual: boolean\n"
            f"- violence: boolean\n\n"
            f'Text to analyze: "{text}"\n\n'
            f"Respond with only the JSON, no other text."
        )

    def _parse_moderation_response(
        self, response_text: str, default_false: dict, default_scores: dict
    ):
        """Parses the moderation response and creates appropriate objects."""
        try:
            parsed = json.loads(response_text.strip())
            flagged = parsed.get("flagged", False)

            categories = ModerationCategories(
                hate=parsed.get("hate", False),
                harassment=parsed.get("harassment", False),
                sexual=parsed.get("sexual", False),
                violence=parsed.get("violence", False),
                **{"self-harm": parsed.get("self_harm", False)},
                **default_false,
            )

            category_scores = ModerationCategoryScores(
                hate=0.1 if parsed.get("hate", False) else 0.01,
                harassment=0.1 if parsed.get("harassment", False) else 0.01,
                sexual=0.1 if parsed.get("sexual", False) else 0.01,
                violence=0.1 if parsed.get("violence", False) else 0.01,
                **{"self-harm": 0.1 if parsed.get("self_harm", False) else 0.01},
                **default_scores,
            )

        except json.JSONDecodeError:
            flagged = any(
                word in response_text.lower()
                for word in ["harmful", "inappropriate", "flagged", "true"]
            )
            categories = ModerationCategories(
                hate=False,
                harassment=False,
                sexual=False,
                violence=False,
                **{"self-harm": False},
                **default_false,
            )
            category_scores = ModerationCategoryScores(
                hate=0.01,
                harassment=0.01,
                sexual=0.01,
                violence=0.01,
                **{"self-harm": 0.01},
                **default_scores,
            )

        return flagged, categories, category_scores

    def _has_image_content(self, messages: List[ChatMessage]) -> bool:
        """Check if any message contains image content."""
        for msg in messages:
            if isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        return True
            elif isinstance(msg.content, str) and "data:image" in msg.content:
                return True
        return False
    def _build_response_format_instruction(self, response_format) -> Optional[str]:
        """Build instruction for response format."""
        if not response_format:
            return None
        if hasattr(response_format, "type"):
            format_type = response_format.type
        else:
            format_type = response_format.get("type")
        if format_type == "json_object":
            return (
                "You must respond with valid JSON only. "
                "Do not include any text before or after the JSON."
            )
        if format_type == "json_schema":
            schema = None
            if hasattr(response_format, "json_schema"):
                schema = response_format.json_schema
            else:
                schema = response_format.get("json_schema", {})
            if schema:
                return (
                    f"You must respond with valid JSON that conforms to this schema: "
                    f"{json.dumps(schema)}"
                )

        return None

    async def list_models(self) -> ModelsResponse:
        """Lists all available models."""
        logger.debug("Listing available models")
        all_models = [
            ModelInfo(
                id=props.get("client_name", poe_model),
                created=int(time.time()),
                owned_by="poe",
            )
            for poe_model, props in MODEL_CATALOG.items()
        ]
        return ModelsResponse(data=all_models)

    def _prepare_messages_for_streaming(
        self, request: ChatCompletionRequest, use_native_tools: bool
    ) -> List[Dict[str, Any]]:
        """Prepare messages for streaming, handling tools injection."""
        messages_list = [msg.model_dump() for msg in request.messages]

        if not use_native_tools and request.tools:
            messages_list = self.tool_handler.inject_tools_into_messages(
                messages_list, request.tools, request.tool_choice
            )

        # Handle response_format
        if request.response_format:
            format_instruction = self._build_response_format_instruction(
                request.response_format
            )
            if format_instruction:
                self._add_system_message(messages_list, format_instruction)

        return messages_list

    def _add_system_message(
        self, messages_list: List[Dict[str, Any]], content: str
    ) -> None:
        """Add content to system message or create new one."""
        for i, msg in enumerate(messages_list):
            if msg.get("role") == "system":
                messages_list[i]["content"] += f"\n\n{content}"
                return

        messages_list.insert(0, {"role": "system", "content": content})

    def _prepare_stop_sequences(
        self, stop: Optional[Union[str, List[str]]]
    ) -> Optional[List[str]]:
        """Convert stop parameter to list of sequences."""
        if not stop:
            return None
        return [stop] if isinstance(stop, str) else stop

    async def _handle_streaming_partial(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        partial,
        request_id: str,
        model: str,
        accumulated_content: List[str],
        thinking_state: Dict[str, bool],
        tool_state: Dict[str, Any],
        request: ChatCompletionRequest,
        use_native_tools: bool,
    ) -> AsyncGenerator[str, None]:
        """Handle a single partial response in streaming."""
        # Handle error responses from Poe
        if hasattr(partial, "error_type") and partial.error_type:
            error_msg = getattr(partial, "text", "An error occurred")
            logger.error("Received error response from Poe: %s - %s", partial.error_type, error_msg)
            # Convert Poe error to OpenAI-compatible error in stream
            error_chunk = {
                "error": {
                    "message": error_msg,
                    "type": partial.error_type,
                    "code": None
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Handle MetaResponse (metadata about the response)
        if type(partial).__name__ == "MetaResponse":
            # Log metadata but don't yield it to the client
            logger.debug("Received MetaResponse: content_type=%s, suggested_replies=%s",
                        getattr(partial, 'content_type', None),
                        getattr(partial, 'suggested_replies', None))
            return

        # Handle attachment URLs
        if hasattr(partial, "attachment") and partial.attachment:
            attachment_text = f"\n![Image]({partial.attachment.url})\n"
            accumulated_content.append(attachment_text)

            chunk = ChatCompletionStreamResponse(
                id=request_id,
                created=int(time.time()),
                model=model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta={"content": attachment_text},
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"
            return

        if not hasattr(partial, "text") or not partial.text:
            return

        accumulated_content.append(partial.text)

        # Handle thinking patterns
        if "Thinking..." in partial.text and not "".join(accumulated_content).startswith(
            "*Thinking...*"
        ):
            async for chunk_str in self._handle_thinking_pattern(
                request_id, model, thinking_state
            ):
                yield chunk_str
            return

        # Check if thinking finished
        if thinking_state["started"] and not thinking_state["finished"]:
            thinking_state["finished"] = True
            chunk = ChatCompletionStreamResponse(
                id=request_id,
                created=int(time.time()),
                model=model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta={"content": "\n\n"},
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

        # Handle tool calls
        if request.tools:
            async for chunk_str in self._handle_tool_streaming(
                partial,
                request_id,
                model,
                tool_state,
                use_native_tools,
            ):
                yield chunk_str
        else:
            # No tools, stream content as-is
            chunk = ChatCompletionStreamResponse(
                id=request_id,
                created=int(time.time()),
                model=model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta={"content": partial.text},
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

    async def _handle_thinking_pattern(
        self, request_id: str, model: str, thinking_state: Dict[str, bool]
    ) -> AsyncGenerator[str, None]:
        """Handle thinking pattern in streaming."""
        if not thinking_state["started"]:
            thinking_state["started"] = True
            chunk = ChatCompletionStreamResponse(
                id=request_id,
                created=int(time.time()),
                model=model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta={"content": "*Thinking...*"},
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

    async def _handle_tool_streaming(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        partial,
        request_id: str,
        model: str,
        tool_state: Dict[str, Any],
        use_native_tools: bool,
    ) -> AsyncGenerator[str, None]:
        """Handle tool calls in streaming."""
        if use_native_tools:
            # Check for native tool calls
            native_tool_calls = (
                self.native_tool_handler.extract_tool_calls_from_message(partial)
            )
            if native_tool_calls:
                tool_state["finish_reason"] = "tool_calls"
                for tool_call in native_tool_calls:
                    chunk = ChatCompletionStreamResponse(
                        id=request_id,
                        created=int(time.time()),
                        model=model,
                        choices=[
                            ChatCompletionStreamChoice(
                                index=0,
                                delta={"tool_calls": [tool_call]},
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                return

            # If no native tool calls but we have text, stream it
            if hasattr(partial, "text") and partial.text:
                chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={"content": partial.text},
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
        else:
            # XML-based tool handling
            filtered_content, tool_calls, new_buffer = (
                self.tool_handler.extract_tool_calls_from_stream(
                    partial.text, tool_state["buffer"]
                )
            )
            tool_state["buffer"] = new_buffer

            if tool_calls:
                tool_state["finish_reason"] = "tool_calls"
                for tool_call in tool_calls:
                    chunk = ChatCompletionStreamResponse(
                        id=request_id,
                        created=int(time.time()),
                        model=model,
                        choices=[
                            ChatCompletionStreamChoice(
                                index=0,
                                delta={"tool_calls": [tool_call]},
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

            if filtered_content:
                chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={"content": filtered_content},
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

    async def create_streaming_response(
        self,
        request: ChatCompletionRequest,
        request_id: str,
        poe_model_name: str,
        attachments: Optional[List["fp.Attachment"]] = None,
    ) -> StreamingResponse:
        """Creates a streaming response for chat completions."""

        async def stream_generator() -> AsyncGenerator[str, None]:
            try:
                logger.info("Starting streaming response for request %s", request_id)

                # Initialize state
                accumulated_content = []
                thinking_state = {"started": False, "finished": False}
                tool_state = {"buffer": "", "finish_reason": "stop"}

                # Setup streaming
                use_native_tools = self.native_tool_handler.should_use_native_tools(
                    poe_model_name, request.tools
                )

                poe_tools = None
                if use_native_tools:
                    poe_tools = self.native_tool_handler.convert_openai_to_poe_tools(
                        request.tools
                    )

                # Prepare messages
                messages_list = self._prepare_messages_for_streaming(
                    request, use_native_tools
                )
                enhanced_messages = [ChatMessage(**msg) for msg in messages_list]
                poe_messages = await PoeClient.convert_to_poe_messages(
                    enhanced_messages, attachments or []
                )

                # Get stop sequences
                stop_sequences = self._prepare_stop_sequences(request.stop)

                # Stream responses
                async for partial in self.poe_client.get_streaming_response(
                    poe_messages, poe_model_name,
                    temperature=request.temperature,
                    stop_sequences=stop_sequences,
                    tools=poe_tools
                ):
                    async for chunk_str in self._handle_streaming_partial(
                        partial,
                        request_id,
                        request.model,
                        accumulated_content,
                        thinking_state,
                        tool_state,
                        request,
                        use_native_tools,
                    ):
                        yield chunk_str

                # Handle final tool calls
                if request.tools and tool_state["buffer"]:
                    _, final_tool_calls = self.tool_handler.parse_tool_calls(
                        "".join(accumulated_content)
                    )
                    if final_tool_calls:
                        tool_state["finish_reason"] = "tool_calls"

                # Send final chunk
                final_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={},
                            finish_reason=tool_state["finish_reason"]
                        )
                    ],
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                logger.info("Completed streaming response for request %s", request_id)

            except PoeAPIError as e:
                logger.error(
                    "Poe API error in streaming for request %s: %s", request_id, e.message
                )
                error_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0, delta={}, finish_reason="error"
                        )
                    ],
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.exception(
                    "Unexpected error in streaming for request %s: %s", request_id, e
                )
                raise StreamingError(str(e), request_id) from e

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )


    def _prepare_messages_for_completion(
        self, request: ChatCompletionRequest, use_native_tools: bool
    ) -> List[Dict[str, Any]]:
        """Prepare messages for non-streaming completion."""
        messages_list = [msg.model_dump() for msg in request.messages]

        # Inject tools if needed
        if not use_native_tools and request.tools:
            messages_list = self.tool_handler.inject_tools_into_messages(
                messages_list, request.tools, request.tool_choice
            )

        # Handle response_format
        if request.response_format:
            format_instruction = self._build_response_format_instruction(
                request.response_format
            )
            if format_instruction:
                self._add_system_message(messages_list, format_instruction)

        # Handle max_tokens instruction
        if request.max_tokens or request.max_completion_tokens:
            max_tokens = request.max_tokens or request.max_completion_tokens
            max_tokens_instruction = (
                f"\nIMPORTANT: Keep your response under {max_tokens} tokens."
            )
            self._add_system_message(messages_list, max_tokens_instruction)

        return messages_list

    async def _get_non_streaming_response(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        request: ChatCompletionRequest,
        request_id: str,
        poe_model_name: str,
        attachments: Optional[List["fp.Attachment"]],
        use_native_tools: bool,
        poe_tools: Optional[List["fp.ToolDefinition"]],
    ) -> ChatCompletionResponse:
        """Get non-streaming response from Poe API."""
        # Prepare messages
        messages_list = self._prepare_messages_for_completion(request, use_native_tools)
        enhanced_messages = [ChatMessage(**msg) for msg in messages_list]
        poe_messages = await PoeClient.convert_to_poe_messages(
            enhanced_messages, attachments or []
        )

        # Get stop sequences
        stop_sequences = self._prepare_stop_sequences(request.stop)

        # Get response
        complete_text, reasoning_tokens = await self.poe_client.get_complete_response(
            poe_messages, poe_model_name,
            temperature=request.temperature,
            stop_sequences=stop_sequences,
            tools=poe_tools
        )

        # Parse tool calls if needed
        cleaned_content = complete_text
        tool_calls = None
        finish_reason = "stop"

        if request.tools and not use_native_tools:
            # Parse XML tool calls
            cleaned_content, parsed_tool_calls = self.tool_handler.parse_tool_calls(
                complete_text
            )
            if parsed_tool_calls:
                tool_calls = parsed_tool_calls
                finish_reason = "tool_calls"
        elif use_native_tools:
            # Native tools are handled during streaming
            logger.info(
                "Native tools used in non-streaming mode - tool calls may be embedded in response"
            )

        # Calculate usage
        usage_kwargs = self._calculate_token_usage(request, complete_text)
        completion_details, prompt_details = self._create_token_details(
            request, reasoning_tokens
        )

        logger.info(
            "Generated response with %d tokens (%d reasoning) for request %s",
            usage_kwargs["completion_tokens"],
            reasoning_tokens,
            request_id,
        )

        # Build response
        assistant_message = ChatMessage(
            role="assistant",
            content=cleaned_content if cleaned_content else None,
            name=None,
            tool_calls=tool_calls,
            tool_call_id=None,
        )

        return ChatCompletionResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=assistant_message,
                    finish_reason=finish_reason,
                    logprobs=None,
                )
            ],
            usage=Usage(
                prompt_tokens=usage_kwargs["prompt_tokens"],
                completion_tokens=usage_kwargs["completion_tokens"],
                total_tokens=usage_kwargs["total_tokens"],
                completion_tokens_details=completion_details,
                prompt_tokens_details=prompt_details,
            ),
        )

    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
        attachments: Optional[List["fp.Attachment"]] = None,
    ) -> Union[ChatCompletionResponse, StreamingResponse]:
        """Creates a chat completion, either streaming or non-streaming."""
        logger.info(
            "Chat completion: model=%s, stream=%s, messages=%d",
            request.model,
            request.stream,
            len(request.messages),
        )

        self._log_request_details(request)
        poe_model_name = self.get_poe_model_name(request.model)

        # Validate model
        try:
            PoeClient.validate_model(poe_model_name)
            logger.info("Model %s validated successfully", poe_model_name)
        except Exception as e:
            logger.error("Model validation failed for %s: %s", poe_model_name, e)
            raise

        request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

        # Handle streaming
        if request.stream:
            return await self.create_streaming_response(
                request, request_id, poe_model_name, attachments
            )

        # Non-streaming response
        use_native_tools = self.native_tool_handler.should_use_native_tools(
            poe_model_name, request.tools
        )

        poe_tools = None
        if use_native_tools:
            poe_tools = self.native_tool_handler.convert_openai_to_poe_tools(
                request.tools
            )

        return await self._get_non_streaming_response(
            request, request_id, poe_model_name, attachments, use_native_tools, poe_tools
        )

    async def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Creates a text completion using Poe, compatible with the OpenAI completions API."""
        prompt_preview = (
            request.prompt[:100] + "..."
            if len(request.prompt) > 100
            else request.prompt
        )
        logger.info(
            "Completion: model=%s, prompt_len=%d", request.model, len(request.prompt)
        )
        logger.debug("Prompt preview: %s", prompt_preview)

        poe_model_name = self.get_poe_model_name(request.model)

        PoeClient.validate_model(poe_model_name)

        chat_messages = [
            ChatMessage(
                role="user",
                content=request.prompt,
                name=None,
                tool_calls=None,
                tool_call_id=None,
            )
        ]
        poe_messages = await PoeClient.convert_to_poe_messages(chat_messages)

        request_id = f"cmpl-{uuid.uuid4().hex[:29]}"

        complete_text, _ = await self.poe_client.get_complete_response(
            poe_messages, poe_model_name
        )

        prompt_tokens = int(len(request.prompt.split()) * WORDS_PER_TOKEN)
        completion_tokens = int(len(complete_text.split()) * WORDS_PER_TOKEN)

        return CompletionResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                CompletionChoice(text=complete_text, index=0, finish_reason="stop")
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def create_moderation(
        self, request: ModerationRequest
    ) -> ModerationResponse:
        """Creates a moderation response using a chat completion for basic content analysis."""  # pylint: disable=line-too-long
        logger.info("Creating moderation using chat completion")
        logger.warning(
            "Moderation endpoint is simulated using LLM analysis. "
            "This is NOT a real content moderation API and should not be used for production safety systems."
        )

        inputs = request.input if isinstance(request.input, list) else [request.input]
        results = []
        default_false, default_scores = self._get_default_moderation_values()

        for text in inputs:
            try:
                moderation_prompt = self._create_moderation_prompt(text)

                chat_messages = [
                    ChatMessage(
                        role="user",
                        content=moderation_prompt,
                        name=None,
                        tool_calls=None,
                        tool_call_id=None,
                    )
                ]
                poe_messages = await PoeClient.convert_to_poe_messages(chat_messages)

                response_text, _ = await self.poe_client.get_complete_response(
                    poe_messages, "gpt-4o-mini"
                )

                flagged, categories, category_scores = self._parse_moderation_response(
                    response_text, default_false, default_scores
                )

                results.append(
                    ModerationResult(
                        flagged=flagged,
                        categories=categories,
                        category_scores=category_scores,
                    )
                )

            except Exception as e:
                logger.error("Moderation failed for text: %s", e)
                raise ModerationError(str(e), text) from e

        return ModerationResponse(
            id=f"modr-{uuid.uuid4().hex[:29]}",
            model=request.model or "text-moderation-latest",
            results=results,
        )
