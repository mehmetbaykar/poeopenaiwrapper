"""Module."""
# pylint: disable=import-error
import logging
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, cast

from .exceptions import PoeAPIError
from .models import (Assistant, AssistantCreateRequest, AssistantListResponse,
                     Run, RunCreateRequest, Thread, ThreadCreateRequest,
                     ThreadMessage)

logger = logging.getLogger(__name__)


class AssistantManager:
    def __init__(self):
        # WARNING: In-memory storage only - data will be lost on server restart
        # This is NOT persistent like OpenAI's Assistant API
        # For production use, implement proper database storage
        logger.warning(
            "Assistant API using in-memory storage. "
            "All assistants, threads, and messages will be lost when the server restarts. "
            "This is NOT equivalent to OpenAI's persistent Assistant API."
        )

        self.assistants_db: Dict[str, Assistant] = {}
        self.threads_db: Dict[str, Thread] = {}
        self.messages_db: Dict[str, List[ThreadMessage]] = {}
        self.runs_db: Dict[str, List[Run]] = {}

    async def create_assistant(self, request: AssistantCreateRequest) -> Assistant:
        """Create a new assistant"""
        assistant_id = f"asst_{uuid.uuid4().hex[:24]}"

        assistant = Assistant(
            id=assistant_id,
            object="assistant",
            created_at=int(time.time()),
            name=request.name,
            description=request.description,
            model=request.model,
            instructions=request.instructions,
            tools=request.tools,
            tool_resources=request.tool_resources,
            metadata=request.metadata,
            temperature=request.temperature,
            top_p=request.top_p,
            response_format=request.response_format
        )

        self.assistants_db[assistant_id] = assistant
        logger.info(f"Created assistant {assistant_id}")
        return assistant

    async def list_assistants(self, limit: int = 20, order: str = "desc") -> AssistantListResponse:
        """List assistants"""
        assistants = list(self.assistants_db.values())

        # Sort by creation time
        if order == "desc":
            assistants.sort(key=lambda x: x.created_at, reverse=True)
        else:
            assistants.sort(key=lambda x: x.created_at)

        # Apply limit
        assistants = assistants[:limit]

        return AssistantListResponse(
            object="list",
            data=assistants,
            first_id=assistants[0].id if assistants else None,
            last_id=assistants[-1].id if assistants else None,
            has_more=len(self.assistants_db) > limit
        )

    async def get_assistant(self, assistant_id: str) -> Assistant:
        """Get an assistant by ID"""
        if assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {assistant_id} not found", 404)
        return self.assistants_db[assistant_id]

    async def update_assistant(self, assistant_id: str, request: AssistantCreateRequest) -> Assistant:
        """Update an assistant"""
        if assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {assistant_id} not found", 404)

        assistant = self.assistants_db[assistant_id]

        # Update fields that are not None
        updates = {
            'name': request.name, 'description': request.description, 'model': request.model,
            'instructions': request.instructions, 'tools': request.tools, 'tool_resources': request.tool_resources,
            'metadata': request.metadata, 'temperature': request.temperature, 'top_p': request.top_p,
            'response_format': request.response_format
        }

        for field, value in updates.items():
            if value is not None:
                setattr(assistant, field, value)

        logger.info(f"Updated assistant {assistant_id}")
        return assistant

    async def delete_assistant(self, assistant_id: str) -> Dict[str, Any]:
        """Delete an assistant"""
        if assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {assistant_id} not found", 404)

        del self.assistants_db[assistant_id]
        logger.info(f"Deleted assistant {assistant_id}")

        return {
            "id": assistant_id,
            "object": "assistant.deleted",
            "deleted": True
        }

    async def create_thread(self, request: ThreadCreateRequest) -> Thread:
        """Create a new thread"""
        thread_id = f"thread_{uuid.uuid4().hex[:24]}"

        thread = Thread(
            id=thread_id,
            object="thread",
            created_at=int(time.time()),
            metadata=request.metadata,
            tool_resources=request.tool_resources
        )

        self.threads_db[thread_id] = thread
        self.messages_db[thread_id] = []

        # Add initial messages if provided
        if request.messages:
            for msg_data in request.messages:
                content = msg_data.get("content", "")
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]

                message = ThreadMessage(
                    id=f"msg_{uuid.uuid4().hex[:24]}",
                    object="thread.message",
                    created_at=int(time.time()),
                    thread_id=thread_id,
                    role=msg_data.get("role", "user"),
                    content=content,
                    attachments=msg_data.get("attachments"),
                    metadata=msg_data.get("metadata")
                )
                self.messages_db[thread_id].append(message)

        logger.info(f"Created thread {thread_id}")
        return thread

    async def get_thread(self, thread_id: str) -> Thread:
        """Get a thread by ID"""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)
        return self.threads_db[thread_id]

    async def delete_thread(self, thread_id: str) -> Dict[str, Any]:
        """Delete a thread"""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        del self.threads_db[thread_id]
        if thread_id in self.messages_db:
            del self.messages_db[thread_id]
        if thread_id in self.runs_db:
            del self.runs_db[thread_id]

        logger.info(f"Deleted thread {thread_id}")

        return {
            "id": thread_id,
            "object": "thread.deleted",
            "deleted": True
        }

    async def create_message(self, thread_id: str, role: str, content: Any,
                           attachments: Optional[List] = None, metadata: Optional[Dict] = None) -> ThreadMessage:
        """Create a message in a thread"""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        message = ThreadMessage(
            id=f"msg_{uuid.uuid4().hex[:24]}",
            object="thread.message",
            created_at=int(time.time()),
            thread_id=thread_id,
            role=cast(Literal["user", "assistant"], role if role in ["user", "assistant"] else "user"),
            content=content if isinstance(content, list) else [{"type": "text", "text": content}],
            attachments=attachments,
            metadata=metadata
        )

        self.messages_db[thread_id].append(message)
        logger.info(f"Created message in thread {thread_id}")
        return message

    async def list_messages(self, thread_id: str, limit: int = 20) -> Dict[str, Any]:
        """List messages in a thread"""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        messages = self.messages_db.get(thread_id, [])
        messages = messages[-limit:]  # Get latest messages

        return {
            "object": "list",
            "data": [msg.model_dump() for msg in messages],
            "first_id": messages[0].id if messages else None,
            "last_id": messages[-1].id if messages else None,
            "has_more": len(self.messages_db.get(thread_id, [])) > limit
        }

    async def create_run(self, thread_id: str, request: RunCreateRequest) -> Run:
        """Create a run (simplified implementation)"""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        if request.assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {request.assistant_id} not found", 404)

        run_id = f"run_{uuid.uuid4().hex[:24]}"

        run = Run(
            id=run_id,
            object="thread.run",
            created_at=int(time.time()),
            thread_id=thread_id,
            assistant_id=request.assistant_id,
            status="completed",  # Simplified - always complete immediately
            required_action=None,
            last_error=None,
            expires_at=None,
            started_at=int(time.time()),
            cancelled_at=None,
            failed_at=None,
            completed_at=int(time.time()),
            model=request.model or self.assistants_db[request.assistant_id].model,
            instructions=request.instructions,
            tools=request.tools,
            metadata=request.metadata,
            usage=None
        )

        if thread_id not in self.runs_db:
            self.runs_db[thread_id] = []
        self.runs_db[thread_id].append(run)

        # NOTE: Assistant responses are simulated - not integrated with Poe API
        # In a full implementation, this would use the Poe client to generate responses
        await self.create_message(
            thread_id=thread_id,
            role="assistant",
            content="[PLACEHOLDER] Assistant API not fully integrated with Poe. This is a mock response for API compatibility."
        )

        logger.info(f"Created run {run_id} for thread {thread_id}")
        return run

    async def get_run(self, thread_id: str, run_id: str) -> Run:
        """Get a run by ID"""
        if thread_id not in self.runs_db:
            raise PoeAPIError(f"No runs found for thread {thread_id}", 404)

        runs = self.runs_db[thread_id]
        for run in runs:
            if run.id == run_id:
                return run

        raise PoeAPIError(f"Run {run_id} not found", 404)

    async def list_runs(self, thread_id: str, limit: int = 20) -> Dict[str, Any]:
        """List runs for a thread"""
        runs = self.runs_db.get(thread_id, [])
        runs = runs[-limit:]  # Get latest runs

        return {
            "object": "list",
            "data": [run.model_dump() for run in runs],
            "first_id": runs[0].id if runs else None,
            "last_id": runs[-1].id if runs else None,
            "has_more": len(self.runs_db.get(thread_id, [])) > limit
        }
