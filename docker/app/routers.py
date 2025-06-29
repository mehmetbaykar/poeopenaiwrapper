"""
API routers for organizing endpoints.
"""

from fastapi import APIRouter, Depends

from .auth import verify_api_key

# Create a router that applies API key verification to all its routes
protected_router = APIRouter(dependencies=[Depends(verify_api_key)])
