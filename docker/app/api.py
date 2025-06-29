"""
FastAPI handlers for OpenAI-compatible endpoints.
"""

import json
import logging
import time
import uuid
from typing import AsyncGenerator, List, Optional, Union

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
from .poe_client import PoeClient

logger = logging.getLogger(__name__)

# Constants for token estimation (rough approximations)
WORDS_PER_TOKEN = 0.75  # Approximate tokens per word
CHARS_PER_TOKEN = 4  # Approximate characters per token


class APIHandler:
    """Handles the core logic of the API endpoints."""

    def __init__(self):
        """Initializes the API handler with a PoeClient instance."""
        self.poe_client = PoeClient()

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

        if request.temperature != 0.0:
            logger.debug("Temperature: %f", request.temperature)
        if request.max_tokens or request.max_completion_tokens:
            logger.debug(
                "Max tokens: %s", request.max_tokens or request.max_completion_tokens
            )
        if request.user:
            logger.debug("User: %s...", request.user[:20])

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

    async def create_streaming_response(
        self,
        request: ChatCompletionRequest,
        request_id: str,
        poe_model_name: str,
    ) -> StreamingResponse:
        """Creates a streaming response for chat completions."""

        async def stream_generator() -> AsyncGenerator[str, None]:
            try:
                logger.info("Starting streaming response for request %s", request_id)
                accumulated_content = ""
                thinking_started = False
                thinking_finished = False
                
                poe_messages = await PoeClient.convert_to_poe_messages(request.messages)

                async for partial in self.poe_client.get_streaming_response(
                    poe_messages, poe_model_name
                ):
                    if not hasattr(partial, "text") or not partial.text:
                        continue

                    accumulated_content += partial.text
                    if "Thinking..." in partial.text and not accumulated_content.startswith(
                        "*Thinking...*"
                    ):
                        if not thinking_started:
                            thinking_started = True
                            thinking_chunk = ChatCompletionStreamResponse(
                                id=request_id,
                                created=int(time.time()),
                                model=request.model,
                                choices=[
                                    ChatCompletionStreamChoice(
                                        index=0,
                                        delta={"content": "*Thinking...*"},
                                        finish_reason=None,
                                    )
                                ],
                            )
                            yield f"data: {thinking_chunk.model_dump_json()}\n\n"
                        continue

                    if thinking_started and not thinking_finished:
                        thinking_finished = True
                        separator_chunk = ChatCompletionStreamResponse(
                            id=request_id,
                            created=int(time.time()),
                            model=request.model,
                            choices=[
                                ChatCompletionStreamChoice(
                                    index=0,
                                    delta={"content": "\n\n"},
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {separator_chunk.model_dump_json()}\n\n"

                    chunk = ChatCompletionStreamResponse(
                        id=request_id,
                        created=int(time.time()),
                        model=request.model,
                        choices=[
                            ChatCompletionStreamChoice(
                                index=0,
                                delta={"content": partial.text},
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

                final_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(index=0, delta={}, finish_reason="stop")
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
                # Convert to specific exception for better error handling
                raise StreamingError(str(e), request_id) from e

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
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

        try:
            PoeClient.validate_model(poe_model_name)
            logger.info("Model %s validated successfully", poe_model_name)
        except Exception as e:
            logger.error("Model validation failed for %s: %s", poe_model_name, e)
            raise

        request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

        if request.stream:
            return await self.create_streaming_response(
                request, request_id, poe_model_name
            )

        poe_messages = await PoeClient.convert_to_poe_messages(
            request.messages, attachments or []
        )
        
        complete_text, reasoning_tokens = await self.poe_client.get_complete_response(
            poe_messages, poe_model_name
        )

        usage_kwargs = self._calculate_token_usage(request, complete_text)
        completion_details, prompt_details = self._create_token_details(request, reasoning_tokens)

        logger.info(
            "Generated response with %d tokens (%d reasoning) for request %s",
            usage_kwargs["completion_tokens"],
            reasoning_tokens,
            request_id,
        )

        assistant_message = ChatMessage(
            role="assistant",
            content=complete_text,
            name=None,
            tool_calls=None,
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
                    finish_reason="stop",
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
        """Creates a moderation response using a chat completion for basic content analysis."""
        logger.info("Creating moderation using chat completion")

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
