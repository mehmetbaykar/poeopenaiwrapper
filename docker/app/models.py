"""Module."""
# pylint: disable=import-error,too-few-public-methods
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# Function calling and tools models
class FunctionParameters(BaseModel):
    type: str = Field("object", description="Type of parameters object")
    properties: Dict[str, Any] = Field(..., description="Properties schema")
    required: Optional[List[str]] = Field(None, description="Required parameters")
    additionalProperties: Optional[bool] = Field(None, description="Allow additional properties")


class FunctionDefinition(BaseModel):
    name: str = Field(..., description="Name of the function")
    description: Optional[str] = Field(None, description="Description of the function")
    parameters: Optional[FunctionParameters] = Field(None, description="Function parameters schema")
    strict: Optional[bool] = Field(None, description="Enable strict schema adherence")


class ChatCompletionFunctionTool(BaseModel):
    type: Optional[Literal["function"]] = Field(None, description="Tool type")
    name: Optional[str] = Field(None, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Tool input schema")
    function: Optional[FunctionDefinition] = Field(None, description="Function definition")


class ChatCompletionToolChoiceOption(BaseModel):
    type: Literal["function"] = Field("function", description="Tool choice type")
    function: Dict[str, str] = Field(..., description="Function choice details")


class ChatCompletionMessageToolCall(BaseModel):
    id: str = Field(..., description="Tool call ID")
    type: Literal["function"] = Field("function", description="Tool call type")
    function: Dict[str, Any] = Field(..., description="Function call details")


class ChatMessage(BaseModel):
    role: str = Field(..., description="The role of the message author")
    content: Optional[Union[str, List[Dict[str, Any]]]] = Field(None, description="The content of the message")
    name: Optional[str] = Field(None, description="The name of the author")
    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = Field(None, description="Tool calls made by assistant")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID for tool responses")


# Response format models
class ResponseFormatJSONSchema(BaseModel):
    type: Literal["json_schema"] = Field("json_schema", description="Response format type")
    json_schema: Dict[str, Any] = Field(..., description="JSON schema definition")


class ResponseFormatJSONObject(BaseModel):
    type: Literal["json_object"] = Field("json_object", description="Response format type")


class ResponseFormatText(BaseModel):
    type: Literal["text"] = Field("text", description="Response format type")


class FileUpload(BaseModel):
    filename: str
    content_type: str
    size: int
    url: Optional[str] = None


class ReasoningConfig(BaseModel):
    effort: Optional[str] = Field(None, description="Reasoning effort (low, medium, high)")


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="ID of the model to use")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(1.0, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    max_completion_tokens: Optional[int] = Field(None, gt=0, description="Maximum completion tokens (for reasoning models)")
    stream: Optional[bool] = Field(False, description="Whether to stream responses")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(0, ge=-2, le=2, description="Presence penalty")
    frequency_penalty: Optional[float] = Field(0, ge=-2, le=2, description="Frequency penalty")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="Logit bias")
    user: Optional[str] = Field(None, description="User identifier")
    files: Optional[List[FileUpload]] = Field(None, description="Uploaded files")
    reasoning_effort: Optional[str] = Field(None, description="Reasoning effort for o1 models (low, medium, high)")
    reasoning: Optional[ReasoningConfig] = Field(None, description="Reasoning configuration for reasoning models")

    # Function calling and tools
    tools: Optional[List[ChatCompletionFunctionTool]] = Field(None, description="Available tools for the model")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool choice strategy")
    parallel_tool_calls: Optional[bool] = Field(None, description="Enable parallel tool calls")

    # Response formatting
    response_format: Optional[Union[ResponseFormatText, ResponseFormatJSONObject, ResponseFormatJSONSchema]] = Field(None, description="Response format specification")

    # Advanced parameters
    top_p: Optional[float] = Field(1.0, ge=0, le=1, description="Nucleus sampling parameter")
    n: Optional[int] = Field(1, ge=1, le=128, description="Number of completions to generate")
    logprobs: Optional[bool] = Field(None, description="Return log probabilities")
    top_logprobs: Optional[int] = Field(None, ge=0, le=20, description="Number of most likely tokens to return")
    seed: Optional[int] = Field(None, description="Random seed for deterministic outputs")
    service_tier: Optional[Literal["auto", "default", "flex"]] = Field(None, description="Service tier for processing")
    store: Optional[bool] = Field(None, description="Store the conversation for model distillation")
    metadata: Optional[Dict[str, str]] = Field(None, description="Metadata for the request")

    # Streaming options
    stream_options: Optional[Dict[str, Any]] = Field(None, description="Streaming configuration options")

    # Modalities (experimental)
    modalities: Optional[List[str]] = Field(None, description="Output modalities (text, audio)")


# Token log probability models
class ChatCompletionTokenLogprob(BaseModel):
    token: str = Field(..., description="The token")
    logprob: float = Field(..., description="Log probability of the token")
    bytes: Optional[List[int]] = Field(None, description="Byte representation of token")
    top_logprobs: Optional[List[Dict[str, Any]]] = Field(None, description="Top alternative tokens")


class ChatCompletionChoiceLogprobs(BaseModel):
    content: Optional[List[ChatCompletionTokenLogprob]] = Field(None, description="Log probabilities for content tokens")
    refusal: Optional[List[ChatCompletionTokenLogprob]] = Field(None, description="Log probabilities for refusal tokens")


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter", "function_call"]] = None
    logprobs: Optional[ChatCompletionChoiceLogprobs] = Field(None, description="Log probability information")


class CompletionTokensDetails(BaseModel):
    reasoning_tokens: Optional[int] = None
    audio_tokens: Optional[int] = None


class PromptTokensDetails(BaseModel):
    cached_tokens: Optional[int] = None
    audio_tokens: Optional[int] = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    completion_tokens_details: Optional[CompletionTokensDetails] = None
    prompt_tokens_details: Optional[PromptTokensDetails] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


class ChatCompletionStreamChoice(BaseModel):
    index: int
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None


class ChatCompletionStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionStreamChoice]


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "poe"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


# Completions API models
class CompletionRequest(BaseModel):
    model: str = Field(..., description="ID of the model to use")
    prompt: str = Field(..., description="The prompt to generate completions for")
    max_tokens: Optional[int] = Field(16, gt=0, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(1.0, ge=0, le=2, description="Sampling temperature")
    top_p: Optional[float] = Field(1.0, ge=0, le=1, description="Nucleus sampling")
    n: Optional[int] = Field(1, ge=1, le=128, description="Number of completions to generate")
    stream: Optional[bool] = Field(False, description="Whether to stream responses")
    logprobs: Optional[int] = Field(None, ge=0, le=5, description="Include log probabilities")
    echo: Optional[bool] = Field(False, description="Echo the prompt in addition to completion")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(0, ge=-2, le=2, description="Presence penalty")
    frequency_penalty: Optional[float] = Field(0, ge=-2, le=2, description="Frequency penalty")
    best_of: Optional[int] = Field(1, ge=1, le=20, description="Generates best_of completions server-side")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="Logit bias")
    user: Optional[str] = Field(None, description="User identifier")


class CompletionChoice(BaseModel):
    text: str
    index: int
    logprobs: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: List[CompletionChoice]
    usage: Usage

# Moderation API models
class ModerationRequest(BaseModel):
    input: Union[str, List[str]] = Field(..., description="Input to classify")
    model: Optional[str] = Field("text-moderation-latest", description="Model to use")


class ModerationCategories(BaseModel):
    hate: bool
    hate_threatening: bool = Field(alias="hate/threatening")
    harassment: bool
    harassment_threatening: bool = Field(alias="harassment/threatening")
    self_harm: bool = Field(alias="self-harm")
    self_harm_intent: bool = Field(alias="self-harm/intent")
    self_harm_instructions: bool = Field(alias="self-harm/instructions")
    sexual: bool
    sexual_minors: bool = Field(alias="sexual/minors")
    violence: bool
    violence_graphic: bool = Field(alias="violence/graphic")


class ModerationCategoryScores(BaseModel):
    hate: float
    hate_threatening: float = Field(alias="hate/threatening")
    harassment: float
    harassment_threatening: float = Field(alias="harassment/threatening")
    self_harm: float = Field(alias="self-harm")
    self_harm_intent: float = Field(alias="self-harm/intent")
    self_harm_instructions: float = Field(alias="self-harm/instructions")
    sexual: float
    sexual_minors: float = Field(alias="sexual/minors")
    violence: float
    violence_graphic: float = Field(alias="violence/graphic")


class ModerationResult(BaseModel):
    flagged: bool
    categories: ModerationCategories
    category_scores: ModerationCategoryScores


class ModerationResponse(BaseModel):
    id: str
    model: str
    results: List[ModerationResult]


# File management models
class FileObject(BaseModel):
    id: str
    object: str = "file"
    bytes: int
    created_at: int
    filename: str
    purpose: str
    status: Optional[str] = None
    status_details: Optional[str] = None


class FileListResponse(BaseModel):
    object: str = "list"
    data: List[FileObject]


class FileDeleteResponse(BaseModel):
    id: str
    object: str = "file"
    deleted: bool


# Assistant API models
class AssistantTool(BaseModel):
    type: Literal["code_interpreter", "file_search", "function"] = Field(..., description="Tool type")
    function: Optional[FunctionDefinition] = Field(None, description="Function definition for function tools")


class AssistantToolResources(BaseModel):
    code_interpreter: Optional[Dict[str, Any]] = Field(None, description="Code interpreter resources")
    file_search: Optional[Dict[str, Any]] = Field(None, description="File search resources")


class Assistant(BaseModel):
    id: str = Field(..., description="Assistant ID")
    object: str = Field("assistant", description="Object type")
    created_at: int = Field(..., description="Creation timestamp")
    name: Optional[str] = Field(None, description="Assistant name")
    description: Optional[str] = Field(None, description="Assistant description")
    model: str = Field(..., description="Model used by assistant")
    instructions: Optional[str] = Field(None, description="System instructions")
    tools: Optional[List[AssistantTool]] = Field(None, description="Available tools")
    tool_resources: Optional[AssistantToolResources] = Field(None, description="Tool resources")
    metadata: Optional[Dict[str, str]] = Field(None, description="Assistant metadata")
    temperature: Optional[float] = Field(None, description="Sampling temperature")
    top_p: Optional[float] = Field(None, description="Nucleus sampling")
    response_format: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Response format")


class AssistantCreateRequest(BaseModel):
    model: str = Field(..., description="Model to use")
    name: Optional[str] = Field(None, description="Assistant name")
    description: Optional[str] = Field(None, description="Assistant description")
    instructions: Optional[str] = Field(None, description="System instructions")
    tools: Optional[List[AssistantTool]] = Field(None, description="Available tools")
    tool_resources: Optional[AssistantToolResources] = Field(None, description="Tool resources")
    metadata: Optional[Dict[str, str]] = Field(None, description="Assistant metadata")
    temperature: Optional[float] = Field(None, description="Sampling temperature")
    top_p: Optional[float] = Field(None, description="Nucleus sampling")
    response_format: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Response format")


class AssistantListResponse(BaseModel):
    object: str = Field("list", description="Object type")
    data: List[Assistant] = Field(..., description="List of assistants")
    first_id: Optional[str] = Field(None, description="First assistant ID")
    last_id: Optional[str] = Field(None, description="Last assistant ID")
    has_more: bool = Field(False, description="Whether there are more assistants")


# Thread models
class ThreadMessage(BaseModel):
    id: str = Field(..., description="Message ID")
    object: str = Field("thread.message", description="Object type")
    created_at: int = Field(..., description="Creation timestamp")
    thread_id: str = Field(..., description="Thread ID")
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: List[Dict[str, Any]] = Field(..., description="Message content")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="File attachments")
    metadata: Optional[Dict[str, str]] = Field(None, description="Message metadata")


class Thread(BaseModel):
    id: str = Field(..., description="Thread ID")
    object: str = Field("thread", description="Object type")
    created_at: int = Field(..., description="Creation timestamp")
    metadata: Optional[Dict[str, str]] = Field(None, description="Thread metadata")
    tool_resources: Optional[AssistantToolResources] = Field(None, description="Tool resources")


class ThreadCreateRequest(BaseModel):
    messages: Optional[List[Dict[str, Any]]] = Field(None, description="Initial messages")
    metadata: Optional[Dict[str, str]] = Field(None, description="Thread metadata")
    tool_resources: Optional[AssistantToolResources] = Field(None, description="Tool resources")


# Run models
class Run(BaseModel):
    id: str = Field(..., description="Run ID")
    object: str = Field("thread.run", description="Object type")
    created_at: int = Field(..., description="Creation timestamp")
    thread_id: str = Field(..., description="Thread ID")
    assistant_id: str = Field(..., description="Assistant ID")
    status: Literal["queued", "in_progress", "requires_action", "cancelling", "cancelled", "failed", "completed", "expired"] = Field(..., description="Run status")
    required_action: Optional[Dict[str, Any]] = Field(None, description="Required action")
    last_error: Optional[Dict[str, Any]] = Field(None, description="Last error")
    expires_at: Optional[int] = Field(None, description="Expiration timestamp")
    started_at: Optional[int] = Field(None, description="Start timestamp")
    cancelled_at: Optional[int] = Field(None, description="Cancellation timestamp")
    failed_at: Optional[int] = Field(None, description="Failure timestamp")
    completed_at: Optional[int] = Field(None, description="Completion timestamp")
    model: str = Field(..., description="Model used")
    instructions: Optional[str] = Field(None, description="Run instructions")
    tools: Optional[List[AssistantTool]] = Field(None, description="Available tools")
    metadata: Optional[Dict[str, str]] = Field(None, description="Run metadata")
    usage: Optional[Usage] = Field(None, description="Token usage")


class RunCreateRequest(BaseModel):
    assistant_id: str = Field(..., description="Assistant ID to use")
    model: Optional[str] = Field(None, description="Model override")
    instructions: Optional[str] = Field(None, description="Instructions override")
    additional_instructions: Optional[str] = Field(None, description="Additional instructions")
    additional_messages: Optional[List[Dict[str, Any]]] = Field(None, description="Additional messages")
    tools: Optional[List[AssistantTool]] = Field(None, description="Tools override")
    metadata: Optional[Dict[str, str]] = Field(None, description="Run metadata")
    temperature: Optional[float] = Field(None, description="Sampling temperature")
    top_p: Optional[float] = Field(None, description="Nucleus sampling")
    stream: Optional[bool] = Field(None, description="Enable streaming")
    max_prompt_tokens: Optional[int] = Field(None, description="Maximum prompt tokens")
    max_completion_tokens: Optional[int] = Field(None, description="Maximum completion tokens")
    truncation_strategy: Optional[Dict[str, Any]] = Field(None, description="Truncation strategy")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool choice strategy")
    parallel_tool_calls: Optional[bool] = Field(None, description="Enable parallel tool calls")
    response_format: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Response format")
