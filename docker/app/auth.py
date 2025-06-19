"""Module."""
# pylint: disable=import-error
import logging
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import LOCAL_API_KEY

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def verify_api_key(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Robust API key verification supporting multiple authentication methods.
    Works with both Cursor IDE and Xcode.
    """
    provided_key = None
    auth_method = None

    # Method 1: Authorization Bearer header (Cursor IDE standard)
    if credentials and credentials.credentials:
        provided_key = credentials.credentials.strip()
        auth_method = "Authorization Bearer"

    # Method 2: x-api-key header (Xcode default)
    elif "x-api-key" in request.headers:
        provided_key = request.headers["x-api-key"].strip()
        auth_method = "x-api-key header"

    # Method 3: Check Authorization header without Bearer prefix
    elif "authorization" in request.headers:
        auth_value = request.headers["authorization"].strip()
        if auth_value.lower().startswith("bearer "):
            provided_key = auth_value[7:].strip()  # Remove "Bearer " prefix
            auth_method = "Authorization Bearer (manual)"
        else:
            provided_key = auth_value
            auth_method = "Authorization (raw)"

    logger.info(f"Auth attempt via {auth_method} for {request.method} {request.url}")

    if not provided_key:
        logger.error("AUTH FAILURE: No API key provided")
        logger.error(f"Available headers: {list(request.headers.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "API key required. Provide it via: Authorization: Bearer YOUR_KEY, x-api-key: YOUR_KEY, or api-key: YOUR_KEY",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "missing_api_key"
                }
            }
        )

    # Validate API key
    if not secrets.compare_digest(provided_key, LOCAL_API_KEY):
        logger.error(f"AUTH FAILURE: Invalid API key via {auth_method}")
        logger.error(f"Provided key length: {len(provided_key)}, Expected key length: {len(LOCAL_API_KEY)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Invalid API key provided. Check your LOCAL_API_KEY configuration.",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key"
                }
            }
        )

    logger.info(f"AUTH SUCCESS: Valid API key via {auth_method}")
    return provided_key
