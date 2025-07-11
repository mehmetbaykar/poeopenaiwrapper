"""
Tool calling handler for Poe API integration.
Provides OpenAI-compatible function calling using prompt engineering.
"""

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import ChatCompletionMessageToolCall, ChatCompletionFunctionTool


class ToolCallHandler:
    """Handles function calling for the Poe API wrapper."""

    def __init__(self):
        self.tool_call_pattern = re.compile(
            r"<tool_call>\s*<name>([^<]+)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>",
            re.DOTALL,
        )

    def inject_tools_into_messages(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ChatCompletionFunctionTool]],
        tool_choice: Optional[Union[str, Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Inject tool definitions into the system message."""
        if not tools:
            return messages

        tools_xml = self._build_tools_xml(tools)
        instructions = self._build_tool_instructions(tool_choice)

        tool_prompt = f"""
{tools_xml}

{instructions}

When using tools, respond with XML in this exact format:
<tool_call>
<name>function_name</name>
<arguments>{{"param": "value"}}</arguments>
</tool_call>

You can make multiple tool calls by using multiple <tool_call> blocks.
IMPORTANT: After using tools, do NOT include the XML tags in your final response to the user.
"""

        # Find existing system message or create new one
        system_msg_idx = None
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                system_msg_idx = i
                break

        if system_msg_idx is not None:
            # Update existing system message
            messages[system_msg_idx]["content"] = (
                tool_prompt + "\n\n" + messages[system_msg_idx].get("content", "")
            )
        else:
            # Insert new system message at the beginning
            messages.insert(0, {"role": "system", "content": tool_prompt})

        return messages

    def _build_tools_xml(self, tools: List[ChatCompletionFunctionTool]) -> str:
        """Build XML representation of tools."""
        tools_parts = ["<tools>"]

        for tool in tools:
            if hasattr(tool, "function") and tool.function:
                func = tool.function
                name = func.name if hasattr(func, "name") else ""
                description = func.description if hasattr(func, "description") else ""
                parameters = func.parameters if hasattr(func, "parameters") else {}

                # Convert parameters to dict if it's a Pydantic model
                if hasattr(parameters, "model_dump"):
                    parameters = parameters.model_dump()

                tools_parts.append(f'<tool name="{name}">')
                if description:
                    tools_parts.append(f"<description>{description}</description>")
                if parameters:
                    params_json = json.dumps(parameters, separators=(",", ":"))
                    tools_parts.append(f"<parameters>{params_json}</parameters>")
                tools_parts.append("</tool>")

        tools_parts.append("</tools>")
        return "\n".join(tools_parts)

    def _build_tool_instructions(
        self, tool_choice: Optional[Union[str, Dict[str, Any]]]
    ) -> str:
        """Build tool usage instructions based on tool_choice."""
        if tool_choice == "none":
            return (
                "IMPORTANT: You are FORBIDDEN from using any tools. Do NOT use <tool_call> tags. "
                "Respond directly with natural language only."
            )
        if tool_choice == "required":
            return "You MUST use at least one tool to answer this request."
        if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            func_name = tool_choice.get("function", {}).get("name", "")
            return f"You MUST use the '{func_name}' function to answer this request."
        # "auto" or None
        return "Use tools when appropriate to help answer the user's request."

    def parse_tool_calls(self, content: str) -> Tuple[str, List[ChatCompletionMessageToolCall]]:
        """
        Parse tool calls from response content.
        Returns (cleaned_content, tool_calls_list)
        """
        if not content:
            return content, []

        tool_calls = []
        matches = list(self.tool_call_pattern.finditer(content))

        if not matches:
            return content, []

        for match in matches:
            name = match.group(1).strip()
            arguments_str = match.group(2).strip()

            # Generate unique ID
            call_id = f"call_{uuid.uuid4().hex[:24]}"

            # Validate JSON arguments
            try:
                json.loads(arguments_str)
            except json.JSONDecodeError:
                # If invalid JSON, try to fix common issues
                arguments_str = self._fix_json_arguments(arguments_str)

            tool_calls.append(
                ChatCompletionMessageToolCall(
                    id=call_id,
                    type="function",
                    function={"name": name, "arguments": arguments_str},
                )
            )

        # Remove tool call XML from content
        cleaned_content = self.tool_call_pattern.sub("", content).strip()
        # Also remove any "Thinking..." patterns that might have leaked through
        cleaned_content = re.sub(
            r"\*?Thinking\.\.\..*?\*?\s*", "", cleaned_content, flags=re.DOTALL
        )
        cleaned_content = re.sub(r"\s{2,}", " ", cleaned_content).strip()

        return cleaned_content, tool_calls

    def _fix_json_arguments(self, arguments_str: str) -> str:
        """Attempt to fix common JSON formatting issues."""
        # Try to fix unquoted keys
        fixed = re.sub(r"(\w+):", r'"\1":', arguments_str)
        # Try to validate again
        try:
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            # If still invalid, wrap in quotes as string
            return json.dumps(arguments_str)

    def extract_tool_calls_from_stream(
        self, chunk_content: str, buffer: str
    ) -> Tuple[str, List[Dict[str, Any]], str]:
        """
        Extract tool calls from streaming content.
        Returns (filtered_content, tool_calls, updated_buffer)
        """
        combined = buffer + chunk_content
        # Check if we have a complete tool call
        tool_calls = []
        filtered_content = chunk_content
        # Look for complete tool call patterns
        start_match = re.search(r"<tool_call>", combined)
        if start_match:
            end_match = re.search(r"</tool_call>", combined)
            if end_match:
                # We have a complete tool call
                _, parsed_calls = self.parse_tool_calls(combined)
                if parsed_calls:
                    # Convert to dict format for streaming
                    for call in parsed_calls:
                        tool_calls.append({
                            "index": 0,
                            "id": call.id,
                            "type": "function",
                            "function": call.function,
                        })
                # Remove the tool call from content
                filtered_content = ""
                buffer = self.tool_call_pattern.sub("", combined).strip()
            else:
                # Incomplete tool call, keep buffering
                filtered_content = ""
                buffer = combined
        else:
            # No tool call pattern, pass through
            buffer = ""

        return filtered_content, tool_calls, buffer
