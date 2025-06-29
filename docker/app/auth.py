"""
Authentication and authorization for the API.
"""

import logging
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import LOCAL_API_KEY


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def verify_api_key(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Verifies the API key from the request headers."""
    provided_key = None
    auth_method = None

    if credentials and credentials.credentials:
        provided_key = credentials.credentials.strip()
        auth_method = "Authorization Bearer"
    elif "x-api-key" in request.headers:
        provided_key = request.headers["x-api-key"].strip()
        auth_method = "x-api-key header"
    elif "authorization" in request.headers:
        auth_value = request.headers["authorization"].strip()
        if auth_value.lower().startswith("bearer "):
            provided_key = auth_value[7:].strip()
            auth_method = "Authorization Bearer (manual)"
        else:
            provided_key = auth_value
            auth_method = "Authorization (raw)"

    logger.info(
        "Auth attempt via %s for %s %s", auth_method, request.method, request.url
    )

    if not provided_key:
        logger.error("AUTH FAILURE: No API key provided")
        logger.error("Available headers: %s", list(request.headers.keys()))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "API key required.",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "missing_api_key",
                }
            },
        )

    if not secrets.compare_digest(provided_key, LOCAL_API_KEY):
        logger.error("AUTH FAILURE: Invalid API key via %s", auth_method)
        logger.error(
            "Provided key length: %d, Expected key length: %d",
            len(provided_key),
            len(LOCAL_API_KEY),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Invalid API key provided.",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            },
        )

    logger.info("AUTH SUCCESS: Valid API key via %s", auth_method)
    return provided_key
