"""
In-memory implementation of the OpenAI Assistants API.

WARNING: This is a mock implementation and does not persist data.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Literal, cast

from .exceptions import PoeAPIError
from .models import (
    Assistant,
    AssistantCreateRequest,
    AssistantListResponse,
    Run,
    RunCreateRequest,
    Thread,
    ThreadCreateRequest,
    ThreadMessage,
)

logger = logging.getLogger(__name__)



class AssistantManager:
    """Manages assistants, threads, messages, and runs in memory."""

    def __init__(self):
        """Initializes the in-memory databases."""
        logger.warning(
            "Assistant API is using in-memory storage. All data will be lost on restart."
        )
        self.assistants_db: Dict[str, Assistant] = {}
        self.threads_db: Dict[str, Thread] = {}
        self.messages_db: Dict[str, List[ThreadMessage]] = {}
        self.runs_db: Dict[str, List[Run]] = {}

    async def create_assistant(self, request: AssistantCreateRequest) -> Assistant:
        """Creates a new assistant and stores it in the in-memory database."""
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
            response_format=request.response_format,
        )
        self.assistants_db[assistant_id] = assistant
        logger.info("Created assistant %s", assistant_id)
        return assistant

    async def list_assistants(
        self, limit: int = 20, order: str = "desc"
    ) -> AssistantListResponse:
        """Lists all assistants, with optional limit and ordering."""
        assistants = list(self.assistants_db.values())
        assistants.sort(key=lambda x: x.created_at, reverse=order == "desc")
        limited_assistants = assistants[:limit]

        return AssistantListResponse(
            object="list",
            data=limited_assistants,
            first_id=limited_assistants[0].id if limited_assistants else None,
            last_id=limited_assistants[-1].id if limited_assistants else None,
            has_more=len(assistants) > limit,
        )

    async def get_assistant(self, assistant_id: str) -> Assistant:
        """Retrieves an assistant by its ID."""
        if assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {assistant_id} not found", 404)
        return self.assistants_db[assistant_id]

    async def update_assistant(
        self, assistant_id: str, request: AssistantCreateRequest
    ) -> Assistant:
        """Updates an existing assistant."""
        if assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {assistant_id} not found", 404)

        assistant = self.assistants_db[assistant_id]
        updates = request.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(assistant, field, value)

        logger.info("Updated assistant %s", assistant_id)
        return assistant

    async def delete_assistant(self, assistant_id: str) -> Dict[str, Any]:
        """Deletes an assistant from the in-memory database."""
        if assistant_id not in self.assistants_db:
            raise PoeAPIError(f"Assistant {assistant_id} not found", 404)

        del self.assistants_db[assistant_id]
        logger.info("Deleted assistant %s", assistant_id)

        return {"id": assistant_id, "object": "assistant.deleted", "deleted": True}


    async def create_thread(self, request: ThreadCreateRequest) -> Thread:
        """Creates a new thread and stores it in the in-memory database."""
        thread_id = f"thread_{uuid.uuid4().hex[:24]}"
        thread = Thread(
            id=thread_id,
            object="thread",
            created_at=int(time.time()),
            metadata=request.metadata,
            tool_resources=request.tool_resources,
        )
        self.threads_db[thread_id] = thread
        self.messages_db[thread_id] = []

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
                    metadata=msg_data.get("metadata"),
                )
                self.messages_db[thread_id].append(message)

        logger.info("Created thread %s", thread_id)
        return thread

    async def get_thread(self, thread_id: str) -> Thread:
        """Retrieves a thread by its ID."""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)
        return self.threads_db[thread_id]

    async def delete_thread(self, thread_id: str) -> Dict[str, Any]:
        """Deletes a thread and its associated messages and runs."""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        del self.threads_db[thread_id]
        self.messages_db.pop(thread_id, None)
        self.runs_db.pop(thread_id, None)

        logger.info("Deleted thread %s", thread_id)

        return {"id": thread_id, "object": "thread.deleted", "deleted": True}

    async def create_message(
        self,
        thread_id: str,
        role: str,
        content: Any,
        **kwargs,
    ) -> ThreadMessage:
        """Creates a new message in a thread."""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        message_content = (
            content if isinstance(content, list) else [{"type": "text", "text": content}]
        )

        message = ThreadMessage(
            id=f"msg_{uuid.uuid4().hex[:24]}",
            object="thread.message",
            created_at=int(time.time()),
            thread_id=thread_id,
            role=cast(Literal["user", "assistant"], role),
            content=message_content,
            attachments=kwargs.get("attachments"),
            metadata=kwargs.get("metadata"),
        )

        self.messages_db[thread_id].append(message)
        logger.info("Created message in thread %s", thread_id)
        return message

    async def list_messages(self, thread_id: str, limit: int = 20) -> Dict[str, Any]:
        """Lists all messages in a thread."""
        if thread_id not in self.threads_db:
            raise PoeAPIError(f"Thread {thread_id} not found", 404)

        messages = self.messages_db.get(thread_id, [])
        limited_messages = messages[-limit:]

        return {
            "object": "list",
            "data": [msg.model_dump() for msg in limited_messages],
            "first_id": limited_messages[0].id if limited_messages else None,
            "last_id": limited_messages[-1].id if limited_messages else None,
            "has_more": len(messages) > limit,
        }

    async def create_run(self, thread_id: str, request: RunCreateRequest) -> Run:
        """Creates a new run for a thread."""
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
            status="completed",
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
            usage=None,
        )

        if thread_id not in self.runs_db:
            self.runs_db[thread_id] = []
        self.runs_db[thread_id].append(run)

        await self.create_message(
            thread_id=thread_id,
            role="assistant",
            content="[PLACEHOLDER] Assistant response.",
        )

        logger.info("Created run %s for thread %s", run_id, thread_id)
        return run

    async def get_run(self, thread_id: str, run_id: str) -> Run:
        """Retrieves a run by its ID."""
        if thread_id not in self.runs_db:
            raise PoeAPIError(f"No runs found for thread {thread_id}", 404)

        for run in self.runs_db[thread_id]:
            if run.id == run_id:
                return run

        raise PoeAPIError(f"Run {run_id} not found", 404)

    async def list_runs(self, thread_id: str, limit: int = 20) -> Dict[str, Any]:
        """Lists all runs for a thread."""
        runs = self.runs_db.get(thread_id, [])
        limited_runs = runs[-limit:]

        return {
            "object": "list",
            "data": [run.model_dump() for run in limited_runs],
            "first_id": limited_runs[0].id if limited_runs else None,
            "last_id": limited_runs[-1].id if limited_runs else None,
            "has_more": len(runs) > limit,
        }
