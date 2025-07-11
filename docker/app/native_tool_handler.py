"""
Native tool handler for Poe API that uses Poe's built-in function calling.
Works with models that have native_tools: True in config.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import fastapi_poe as fp

from .models import ChatCompletionFunctionTool
from .config import MODEL_CATALOG

logger = logging.getLogger(__name__)


class NativeToolHandler:
    """Handles function calling using Poe's native tool support."""

    @staticmethod
    def supports_native_tools(model: str) -> bool:
        """Check if a model supports native Poe function calling."""
        # Check config for native_tools support
        for client_name, props in MODEL_CATALOG.items():
            if (props.get("poe_name") == model or props.get("client_name") == model or
                    client_name == model):
                return props.get("native_tools", False)
        return False

    @staticmethod
    def convert_openai_to_poe_tools(
        tools: List[ChatCompletionFunctionTool]
    ) -> List[fp.ToolDefinition]:
        """Convert OpenAI tool definitions to Poe format."""
        poe_tools = []

        for tool in tools:
            if tool.type != "function":
                continue

            function = tool.function

            # Convert to Poe's expected format
            tool_dict = {
                "type": "function",
                "function": {
                    "name": function.name,
                    "description": function.description,
                    "parameters": (function.parameters.model_dump()
                                   if hasattr(function.parameters, 'model_dump')
                                   else function.parameters)
                }
            }

            try:
                poe_tool = fp.ToolDefinition(**tool_dict)
                poe_tools.append(poe_tool)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to convert tool %s to Poe format: %s", function.name, e)

        return poe_tools

    @staticmethod
    def extract_tool_calls_from_message(
            message: fp.PartialResponse
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from a Poe message response."""
        if not hasattr(message, 'data') or not message.data:
            return None

        # Check if this is a tool call response
        if isinstance(message.data, dict) and 'tool_calls' in message.data:
            tool_calls = []
            for tc in message.data['tool_calls']:
                tool_call = {
                    "id": tc.get('id', f"call_{len(tool_calls)}"),
                    "type": "function",
                    "function": {
                        "name": tc['function']['name'],
                        "arguments": tc['function']['arguments']
                    }
                }
                tool_calls.append(tool_call)
            return tool_calls

        return None

    @staticmethod
    def format_tool_response(
            tool_call_id: str, function_name: str, response: Any
    ) -> Dict[str, Any]:
        """Format a tool response in OpenAI format."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": function_name,
            "content": json.dumps(response) if not isinstance(response, str) else response
        }

    @staticmethod
    def should_use_native_tools(
            model: str, tools: Optional[List[ChatCompletionFunctionTool]]
    ) -> bool:
        """Determine if native tools should be used."""
        if not tools:
            return False

        if not NativeToolHandler.supports_native_tools(model):
            logger.info(
                "Model %s does not support native Poe function calling. Using XML fallback.", model
            )
            return False

        logger.info("Model %s supports native Poe function calling. Using native tools.", model)
        return True
