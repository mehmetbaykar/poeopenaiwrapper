"""
Main application file for the FastAPI server.
"""

import json
import os
import time
import traceback
from typing import List

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .api import APIHandler
from .assistants import AssistantManager
from .exceptions import (
    FileUploadError,
    PoeAPIError,
    file_upload_exception_handler,
    general_exception_handler,
    http_exception_handler,
    poe_api_exception_handler,
    validation_exception_handler,
)
from .file_handler import FileManager
from .logging_config import setup_logging
from .models import (
    AssistantCreateRequest,
    ChatCompletionRequest,
    CompletionRequest,
    ModelsResponse,
    ModerationRequest,
    RunCreateRequest,
    ThreadCreateRequest,
)
from .routers import protected_router

# --- Logging Setup ---

logger = setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))


# --- Middleware ---


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log incoming requests and outgoing responses."""

    async def dispatch(self, request: Request, call_next):
        """Dispatches the request and logs timing information."""
        start_time = time.time()
        logger.info("Request: %s %s", request.method, request.url)

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                "Response: %d (%.3fs)", response.status_code, process_time
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error("Request failed after %.3fs: %s", process_time, e)
            logger.error("Full traceback: %s", traceback.format_exc())
            raise

    def log_request_details(self, request: Request):
        """Logs detailed request information for debugging."""
        logger.debug("Request headers: %s", dict(request.headers))
        logger.debug("Request path: %s", request.url.path)


# --- FastAPI App Initialization ---

app = FastAPI(
    title="Poe-OpenAI-Wrapper",
    description="An OpenAI-compatible API wrapper for Poe.com.",
    version="0.1.0",
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(PoeAPIError, poe_api_exception_handler)
app.add_exception_handler(FileUploadError, file_upload_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# --- API Handlers ---

api_handler = APIHandler()
file_manager = FileManager()
assistant_manager = AssistantManager()


# --- Public API Endpoints ---


@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "Poe-OpenAI-Wrapper is running.",
        "version": app.version,
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": int(time.time())}


# --- Protected API Endpoints ---


@protected_router.get("/models", response_model=ModelsResponse)
async def list_models():
    """Lists all available models."""
    return await api_handler.list_models()


@protected_router.post("/chat/completions")
async def create_chat_completion(request: Request):
    """Creates a chat completion, with or without file attachments."""
    attachments = []
    content_type = request.headers.get("content-type", "")
    
    logger.info("Chat completion request with content-type: %s", content_type)

    if "multipart/form-data" in content_type:
        logger.info("Processing multipart form data request")
        form = await request.form()
        
        # Log all form fields
        logger.debug("Form fields: %s", list(form.keys()))
        
        request_json_str = form.get("request")
        if not request_json_str or not isinstance(request_json_str, str):
            raise PoeAPIError(
                "Multipart request must have a 'request' field with JSON data.", 400
            )
        try:
            request_data = json.loads(request_json_str)
            chat_request = ChatCompletionRequest(**request_data)
        except (json.JSONDecodeError, ValueError) as e:
            raise PoeAPIError(f"Invalid JSON in 'request' form field: {e}", 400) from e

        form_files = form.getlist("files")
        logger.info("Found %d files in form data", len(form_files))
        
        if form_files:
            upload_files = [f for f in form_files if isinstance(f, UploadFile)]
            logger.info("Processing %d upload files", len(upload_files))
            attachments = await file_manager.process_files(upload_files)
            logger.info("Created %d attachments from files", len(attachments))

    elif "application/json" in content_type:
        logger.info("Processing JSON request")
        try:
            request_data = await request.json()
            chat_request = ChatCompletionRequest(**request_data)
        except json.JSONDecodeError as e:
            raise PoeAPIError(f"Invalid JSON body: {e}", 400) from e
    else:
        raise PoeAPIError(f"Unsupported content-type: {content_type}", 415)

    logger.info("Calling create_chat_completion with %d attachments", len(attachments))
    return await api_handler.create_chat_completion(chat_request, attachments)


@protected_router.post("/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Uploads one or more files."""
    attachments = await file_manager.process_files(files)
    return {
        "uploaded_files": len(attachments),
        "files": [{"filename": f.filename} for f in files],
    }


@protected_router.post("/completions")
async def create_completion(request: CompletionRequest):
    """Creates a text completion."""
    return await api_handler.create_completion(request)


@protected_router.post("/moderations")
async def create_moderation(request: ModerationRequest):
    """Creates a moderation request."""
    return await api_handler.create_moderation(request)


@protected_router.get("/files")
async def list_files():
    """Lists all uploaded files."""
    return await file_manager.list_files()


@protected_router.get("/files/{file_id}")
async def get_file(file_id: str):
    """Retrieves a file by its ID."""
    return await file_manager.get_file(file_id)


@protected_router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Deletes a file by its ID."""
    return await file_manager.delete_file(file_id)


# --- Assistant API Endpoints ---


@protected_router.post("/assistants")
async def create_assistant(request: AssistantCreateRequest):
    """Creates an assistant."""
    return await assistant_manager.create_assistant(request)


@protected_router.get("/assistants")
async def list_assistants(limit: int = 20, order: str = "desc"):
    """Lists all assistants."""
    return await assistant_manager.list_assistants(limit=limit, order=order)


@protected_router.get("/assistants/{assistant_id}")
async def get_assistant(assistant_id: str):
    """Retrieves an assistant by its ID."""
    return await assistant_manager.get_assistant(assistant_id)


@protected_router.post("/assistants/{assistant_id}")
async def update_assistant(assistant_id: str, request: AssistantCreateRequest):
    """Updates an assistant."""
    return await assistant_manager.update_assistant(assistant_id, request)


@protected_router.delete("/assistants/{assistant_id}")
async def delete_assistant(assistant_id: str):
    """Deletes an assistant by its ID."""
    return await assistant_manager.delete_assistant(assistant_id)


# --- Thread API Endpoints ---


@protected_router.post("/threads")
async def create_thread(request: ThreadCreateRequest):
    """Creates a thread."""
    return await assistant_manager.create_thread(request)


@protected_router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Retrieves a thread by its ID."""
    return await assistant_manager.get_thread(thread_id)


@protected_router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Deletes a thread by its ID."""
    return await assistant_manager.delete_thread(thread_id)


@protected_router.get("/threads/{thread_id}/messages")
async def list_messages(thread_id: str, limit: int = 20):
    """Lists all messages in a thread."""
    return await assistant_manager.list_messages(thread_id, limit=limit)


@protected_router.post("/threads/{thread_id}/messages")
async def create_message(thread_id: str, request: dict):
    """Creates a message in a thread."""
    return await assistant_manager.create_message(
        thread_id=thread_id,
        role=request.get("role", "user"),
        content=request.get("content"),
        attachments=request.get("attachments"),
        metadata=request.get("metadata"),
    )


@protected_router.post("/threads/{thread_id}/runs")
async def create_run(thread_id: str, request: RunCreateRequest):
    """Creates a run for a thread."""
    return await assistant_manager.create_run(thread_id, request)


@protected_router.get("/threads/{thread_id}/runs")
async def list_runs(thread_id: str, limit: int = 20):
    """Lists all runs for a thread."""
    return await assistant_manager.list_runs(thread_id, limit=limit)


@protected_router.get("/threads/{thread_id}/runs/{run_id}")
async def get_run(thread_id: str, run_id: str):
    """Retrieves a run by its ID."""
    return await assistant_manager.get_run(thread_id, run_id)


# --- App Configuration ---

app.include_router(protected_router, prefix="/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
