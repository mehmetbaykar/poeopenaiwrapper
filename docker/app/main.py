"""Module."""
# pylint: disable=import-error
import os
import time
from typing import List

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .api import APIHandler
from .assistants import AssistantManager
from .auth import verify_api_key
from .exceptions import (FileUploadError, PoeAPIError,
                         file_upload_exception_handler,
                         general_exception_handler, http_exception_handler,
                         poe_api_exception_handler,
                         validation_exception_handler)
from .file_handler import FileManager
from .logging_config import setup_logging
from .models import (AssistantCreateRequest, ChatCompletionRequest,
                     CompletionRequest, ModelsResponse, ModerationRequest,
                     RunCreateRequest, ThreadCreateRequest)

logger = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="logs/app.log"
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url}")

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(f"Response: {response.status_code} ({process_time:.3f}s)")
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Request failed after {process_time:.3f}s: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise


app = FastAPI(
    title="OpenAI Compatible API",
    description="Local OpenAI-compatible API server",
    version="0.0.1"
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(PoeAPIError, poe_api_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(FileUploadError, file_upload_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, general_exception_handler)

api_handler = APIHandler()
file_manager = FileManager()
assistant_manager = AssistantManager()

@app.get("/")
async def root():
    return {
        "message": "Poe Wrapper API",
        "version": "0.0.1",
        "endpoints": [
            "/v1/models",
            "/v1/chat/completions",
            "/v1/completions",
            "/v1/moderations",
            "/v1/files",
            "/v1/assistants",
            "/v1/threads"
        ]
    }


@app.get("/v1/models", response_model=ModelsResponse)
async def list_models(api_key: str = Depends(verify_api_key)):
    return await api_handler.list_models()


@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    attachments = []
    return await api_handler.create_chat_completion(request, attachments)


@app.post("/v1/chat/completions/with-files")
async def create_chat_completion_with_files(
    request: str = Form(...),
    files: List[UploadFile] = File(...),
    api_key: str = Depends(verify_api_key)
):
    import json
    try:
        request_data = json.loads(request)
        chat_request = ChatCompletionRequest(**request_data)
    except (json.JSONDecodeError, ValueError) as e:
        from .exceptions import PoeAPIError
        raise PoeAPIError(f"Invalid JSON in request field: {str(e)}", 400)

    attachments = await file_manager.process_files(files)
    return await api_handler.create_chat_completion(chat_request, attachments)


@app.post("/v1/files/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    api_key: str = Depends(verify_api_key)
):
    attachments = await file_manager.process_files(files)
    return {
        "uploaded_files": len(attachments),
        "files": [{"filename": f.filename} for f in files]
    }


@app.post("/v1/completions")
async def create_completion(
    request: CompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    return await api_handler.create_completion(request)

@app.post("/v1/moderations")
async def create_moderation(
    request: ModerationRequest,
    api_key: str = Depends(verify_api_key)
):
    return await api_handler.create_moderation(request)


@app.get("/v1/files")
async def list_files(
    api_key: str = Depends(verify_api_key)
):
    return await file_manager.list_files()


@app.get("/v1/files/{file_id}")
async def get_file(
    file_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await file_manager.get_file(file_id)


@app.delete("/v1/files/{file_id}")
async def delete_file(
    file_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await file_manager.delete_file(file_id)


# Assistant API endpoints
@app.post("/v1/assistants")
async def create_assistant(
    request: AssistantCreateRequest,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.create_assistant(request)


@app.get("/v1/assistants")
async def list_assistants(
    limit: int = 20,
    order: str = "desc",
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.list_assistants(limit=limit, order=order)


@app.get("/v1/assistants/{assistant_id}")
async def get_assistant(
    assistant_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.get_assistant(assistant_id)


@app.post("/v1/assistants/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    request: AssistantCreateRequest,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.update_assistant(assistant_id, request)


@app.delete("/v1/assistants/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.delete_assistant(assistant_id)


# Thread API endpoints
@app.post("/v1/threads")
async def create_thread(
    request: ThreadCreateRequest,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.create_thread(request)


@app.get("/v1/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.get_thread(thread_id)


@app.delete("/v1/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.delete_thread(thread_id)


@app.get("/v1/threads/{thread_id}/messages")
async def list_messages(
    thread_id: str,
    limit: int = 20,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.list_messages(thread_id, limit=limit)


@app.post("/v1/threads/{thread_id}/messages")
async def create_message(
    thread_id: str,
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.create_message(
        thread_id=thread_id,
        role=request.get("role", "user"),
        content=request.get("content"),
        attachments=request.get("attachments"),
        metadata=request.get("metadata")
    )


@app.post("/v1/threads/{thread_id}/runs")
async def create_run(
    thread_id: str,
    request: RunCreateRequest,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.create_run(thread_id, request)


@app.get("/v1/threads/{thread_id}/runs")
async def list_runs(
    thread_id: str,
    limit: int = 20,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.list_runs(thread_id, limit=limit)


@app.get("/v1/threads/{thread_id}/runs/{run_id}")
async def get_run(
    thread_id: str,
    run_id: str,
    api_key: str = Depends(verify_api_key)
):
    return await assistant_manager.get_run(thread_id, run_id)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": int(time.time())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
