"""
Custom exception classes and exception handlers for the application.
"""

import logging
from typing import Union

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


class PoeAPIError(Exception):
    """Custom exception for errors related to the Poe API."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class FileUploadError(Exception):
    """Custom exception for errors related to file uploads."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ModelValidationError(PoeAPIError):
    """Exception raised when model validation fails."""

    def __init__(self, model: str, available_models: list):
        message = f"Model '{model}' not available. Available models: {available_models}"
        super().__init__(message, 400)
        self.model = model
        self.available_models = available_models


class AuthenticationError(PoeAPIError):
    """Exception raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class StreamingError(PoeAPIError):
    """Exception raised when streaming fails."""

    def __init__(self, message: str, request_id: str):
        super().__init__(f"Streaming error for request {request_id}: {message}", 500)
        self.request_id = request_id


class ModerationError(PoeAPIError):
    """Exception raised when moderation processing fails."""

    def __init__(self, message: str, text: str = ""):
        super().__init__(f"Moderation error: {message}", 500)
        self.text = text


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handles validation errors for incoming requests."""
    logger.error("Validation error for %s: %s", request.url, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Invalid request format.",
                "type": "validation_error",
                "details": exc.errors(),
            }
        },
    )


async def http_exception_handler(
    request: Request, exc: Union[HTTPException, StarletteHTTPException]
) -> JSONResponse:
    """Handles generic HTTP exceptions."""
    logger.error("HTTP error for %s: %s", request.url, exc.detail)

    if exc.status_code == 401 and isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "http_error",
                "code": exc.status_code,
            }
        },
    )


async def poe_api_exception_handler(
    request: Request, exc: PoeAPIError
) -> JSONResponse:
    """Handles exceptions specific to the Poe API."""
    logger.error("Poe API error for %s: %s", request.url, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": "poe_api_error",
                "code": exc.status_code,
            }
        },
    )


async def file_upload_exception_handler(
    request: Request, exc: FileUploadError
) -> JSONResponse:
    """Handles exceptions specific to file uploads."""
    logger.error("File upload error for %s: %s", request.url, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": "file_upload_error",
                "code": exc.status_code,
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles all other unexpected exceptions."""
    logger.exception("Unexpected error for %s: %s", request.url, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An unexpected internal server error occurred.",
                "type": "internal_server_error",
                "code": 500,
            }
        },
    )
