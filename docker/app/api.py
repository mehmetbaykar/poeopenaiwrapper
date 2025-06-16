import time
import uuid
from typing import List, AsyncGenerator, Union, Optional
from fastapi.responses import StreamingResponse
from .models import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatCompletionStreamResponse, ChatCompletionStreamChoice, ChatMessage,
    ModelsResponse, ModelInfo, Usage, CompletionTokensDetails, PromptTokensDetails,
    CompletionRequest, CompletionResponse, CompletionChoice,
    ModerationRequest, ModerationResponse, ModerationResult, ModerationCategories, ModerationCategoryScores
)
from .poe_client import PoeClient
from .exceptions import PoeAPIError
from .config import MODEL_CATALOG, get_poe_name_for_client
import logging

logger = logging.getLogger(__name__)


class APIHandler:
    def __init__(self):
        self.poe_client = PoeClient()
    
    def get_poe_model_name(self, client_name: str) -> str:
        """Convert client display name back to POE model name for API calls."""
        poe_name = get_poe_name_for_client(client_name)
        logger.debug(f"Model name mapping: {client_name} -> {poe_name}")
        return poe_name

    async def list_models(self) -> ModelsResponse:
        logger.debug("Listing available models")
        all_models = []
        
        # Add Poe-supported models with client display names
        for poe_model, props in MODEL_CATALOG.items():
            client_name = props.get("client_name", poe_model)
            all_models.append(ModelInfo(
                id=client_name,
                created=int(time.time()),
                owned_by="poe"
            ))
        
        return ModelsResponse(data=all_models)


    async def create_streaming_response(
        self,
        request: ChatCompletionRequest,
        poe_messages: List,
        request_id: str,
        poe_model_name: str
    ) -> StreamingResponse:
        async def stream_generator() -> AsyncGenerator[str, None]:
            try:
                logger.info(f"Starting streaming response for request {request_id}")
                accumulated_content = ""
                thinking_started = False
                thinking_finished = False
                
                async for partial in self.poe_client.get_streaming_response(poe_messages, poe_model_name):
                    if hasattr(partial, 'text') and partial.text:
                        accumulated_content += partial.text
                        
                        # Check if this chunk contains raw "Thinking..." noise
                        if "Thinking..." in partial.text and not accumulated_content.startswith("*Thinking...*"):
                            # First time we see thinking noise, send the "*Thinking...*" header
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
                                            finish_reason=None
                                        )
                                    ]
                                )
                                yield f"data: {thinking_chunk.model_dump_json()}\n\n"
                            # Skip the actual "Thinking..." noise chunk
                            continue
                        else:
                            # This is clean content
                            if thinking_started and not thinking_finished:
                                # Send the separator between thinking and content
                                thinking_finished = True
                                separator_chunk = ChatCompletionStreamResponse(
                                    id=request_id,
                                    created=int(time.time()),
                                    model=request.model,
                                    choices=[
                                        ChatCompletionStreamChoice(
                                            index=0,
                                            delta={"content": "\n\n"},
                                            finish_reason=None
                                        )
                                    ]
                                )
                                yield f"data: {separator_chunk.model_dump_json()}\n\n"
                            
                            # Send the clean content
                            chunk = ChatCompletionStreamResponse(
                                id=request_id,
                                created=int(time.time()),
                                model=request.model,
                                choices=[
                                    ChatCompletionStreamChoice(
                                        index=0,
                                        delta={"content": partial.text},
                                        finish_reason=None
                                    )
                                ]
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"
                
                final_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={},
                            finish_reason="stop"
                        )
                    ]
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                logger.info(f"Completed streaming response for request {request_id}")
                
            except PoeAPIError as e:
                logger.error(f"Poe API error in streaming for request {request_id}: {e.message}")
                error_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={},
                            finish_reason="error"
                        )
                    ]
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.exception(f"Unexpected error in streaming for request {request_id}: {e}")
                error_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={},
                            finish_reason="error"
                        )
                    ]
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )

    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
        attachments: Optional[List] = None
    ) -> Union[ChatCompletionResponse, StreamingResponse]:
        logger.info(f"Chat completion: model={request.model}, stream={request.stream}, messages={len(request.messages)}")

        message_summary = []
        for msg in request.messages:
            message_summary.append(f"{msg.role}({len(str(msg.content)) if msg.content else 0})")
        logger.debug(f"Messages: [{', '.join(message_summary)}]")
        
        if request.temperature != 0.0:
            logger.debug(f"Temperature: {request.temperature}")
        if request.max_tokens or request.max_completion_tokens:
            logger.debug(f"Max tokens: {request.max_tokens or request.max_completion_tokens}")
        if request.user:
            logger.debug(f"User: {request.user[:20]}...")
        
        poe_model_name = self.get_poe_model_name(request.model)
        
        try:
            PoeClient.validate_model(poe_model_name)
            logger.info(f"Model {poe_model_name} validated successfully")
        except Exception as e:
            logger.error(f"Model validation failed for {poe_model_name}: {e}")
            raise
        
        poe_messages = PoeClient.convert_to_poe_messages(request.messages, attachments or [])
        request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        
        if request.stream:
            # Update request with POE model name for streaming but keep display name for response
            modified_request = request.model_copy()
            modified_request.model = poe_model_name
            return await self.create_streaming_response(request, poe_messages, request_id, poe_model_name)
        
        # Get response from Poe (raw content, with reasoning token estimation) using POE model name
        complete_text, reasoning_tokens = await self.poe_client.get_complete_response(poe_messages, poe_model_name)
        
        # IMPORTANT: Always forward the complete raw response from Poe
        # Do not modify or filter the content - let the client handle it
        # No parsing needed - just forward everything raw
        
        prompt_tokens = sum(len(str(msg.content).split()) if msg.content else 0 for msg in request.messages)
        completion_tokens = len(complete_text.split())
        
        # Create usage object with reasoning tokens for o1 models
        usage_kwargs = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        
        # Add reasoning token details for reasoning models
        completion_details = None
        prompt_details = None
        if PoeClient.is_reasoning_model(request.model):
            completion_details = CompletionTokensDetails(
                reasoning_tokens=reasoning_tokens,
                audio_tokens=None
            )
            prompt_details = PromptTokensDetails(
                cached_tokens=0,
                audio_tokens=None
            )
        
        logger.info(f"Generated response with {completion_tokens} tokens ({reasoning_tokens} reasoning) for request {request_id}")
        
        # Create assistant message - always raw content, no tool calls
        assistant_message = ChatMessage(
            role="assistant",
            content=complete_text,
            name=None,
            tool_calls=None,
            tool_call_id=None
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
                    logprobs=None
                )
            ],
            usage=Usage(
                prompt_tokens=usage_kwargs["prompt_tokens"],
                completion_tokens=usage_kwargs["completion_tokens"],
                total_tokens=usage_kwargs["total_tokens"],
                completion_tokens_details=completion_details,
                prompt_tokens_details=prompt_details
            )
        )

    async def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create a text completion using Poe, compatible with OpenAI completions API"""
        prompt_preview = request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt
        logger.info(f"Completion: model={request.model}, prompt_len={len(request.prompt)}")
        logger.debug(f"Prompt preview: {prompt_preview}")
        
        # Convert display name to POE model name
        poe_model_name = self.get_poe_model_name(request.model)
        
        PoeClient.validate_model(poe_model_name)
        
        # Convert prompt to chat format for Poe
        chat_messages = [ChatMessage(role="user", content=request.prompt, name=None, tool_calls=None, tool_call_id=None)]
        poe_messages = PoeClient.convert_to_poe_messages(chat_messages)
        
        request_id = f"cmpl-{uuid.uuid4().hex[:29]}"
        
        # Get response from Poe using POE model name
        complete_text, reasoning_tokens = await self.poe_client.get_complete_response(poe_messages, poe_model_name)
        
        prompt_tokens = len(request.prompt.split())
        completion_tokens = len(complete_text.split())
        
        return CompletionResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                CompletionChoice(
                    text=complete_text,
                    index=0,
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

    async def create_moderation(self, request: ModerationRequest) -> ModerationResponse:
        """Create moderation - Use chat completion for basic content moderation"""
        logger.info("Creating moderation using chat completion")
        
        inputs = request.input if isinstance(request.input, list) else [request.input]
        results = []
        
        # Define default values outside the loop
        default_false = {"hate/threatening": False, "harassment/threatening": False, 
                        "self-harm/intent": False, "self-harm/instructions": False,
                        "sexual/minors": False, "violence/graphic": False}
        default_scores = {"hate/threatening": 0.01, "harassment/threatening": 0.01,
                         "self-harm/intent": 0.01, "self-harm/instructions": 0.01,
                         "sexual/minors": 0.01, "violence/graphic": 0.01}
        
        for text in inputs:
            try:
                # Use chat completion to analyze content
                moderation_prompt = f"""Analyze this text for harmful content. Respond with JSON containing:
- flagged: boolean (true if content is harmful)
- hate: boolean
- harassment: boolean  
- self_harm: boolean
- sexual: boolean
- violence: boolean

Text to analyze: "{text}"

Respond with only the JSON, no other text."""

                chat_messages = [ChatMessage(role="user", content=moderation_prompt, name=None, tool_calls=None, tool_call_id=None)]
                poe_messages = PoeClient.convert_to_poe_messages(chat_messages)
                
                response_text, _ = await self.poe_client.get_complete_response(poe_messages, "gpt-4o-mini")
                
                # Try to parse JSON response
                import json
                try:
                    parsed = json.loads(response_text.strip())
                    flagged = parsed.get("flagged", False)
                    
                    # Create moderation categories with mock scores
                    categories = ModerationCategories(
                        hate=parsed.get("hate", False), harassment=parsed.get("harassment", False),
                        sexual=parsed.get("sexual", False), violence=parsed.get("violence", False),
                        **{"self-harm": parsed.get("self_harm", False)}, **default_false
                    )
                    
                    # Mock category scores (0.0 to 1.0)
                    category_scores = ModerationCategoryScores(
                        hate=0.1 if parsed.get("hate", False) else 0.01,
                        harassment=0.1 if parsed.get("harassment", False) else 0.01,
                        sexual=0.1 if parsed.get("sexual", False) else 0.01,
                        violence=0.1 if parsed.get("violence", False) else 0.01,
                        **{"self-harm": 0.1 if parsed.get("self_harm", False) else 0.01}, **default_scores
                    )
                    
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    flagged = any(word in response_text.lower() for word in ["harmful", "inappropriate", "flagged", "true"])
                    categories = ModerationCategories(
                        hate=False, harassment=False, sexual=False, violence=False,
                        **{"self-harm": False}, **default_false
                    )
                    category_scores = ModerationCategoryScores(
                        hate=0.01, harassment=0.01, sexual=0.01, violence=0.01,
                        **{"self-harm": 0.01}, **default_scores
                    )
                
                results.append(ModerationResult(
                    flagged=flagged,
                    categories=categories,
                    category_scores=category_scores
                ))
                
            except Exception as e:
                logger.error(f"Moderation failed for text: {e}")
                # Default safe response
                safe_categories = ModerationCategories(
                    hate=False, harassment=False, sexual=False, violence=False,
                    **{"self-harm": False}, **{"hate/threatening": False, "harassment/threatening": False,
                    "self-harm/intent": False, "self-harm/instructions": False,
                    "sexual/minors": False, "violence/graphic": False}
                )
                safe_scores = ModerationCategoryScores(
                    hate=0.01, harassment=0.01, sexual=0.01, violence=0.01,
                    **{"self-harm": 0.01}, **{"hate/threatening": 0.01, "harassment/threatening": 0.01,
                    "self-harm/intent": 0.01, "self-harm/instructions": 0.01,
                    "sexual/minors": 0.01, "violence/graphic": 0.01}
                )
                results.append(ModerationResult(flagged=False, categories=safe_categories, category_scores=safe_scores))
        
        return ModerationResponse(
            id=f"modr-{uuid.uuid4().hex[:29]}",
            model=request.model or "text-moderation-latest",
            results=results
        )