"""
Handles file uploads, validation, and interaction with the Poe API.
"""

import asyncio
import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Generator, List, Optional

import fastapi_poe as fp
from fastapi import UploadFile

from .config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_MB, POE_API_KEY
from .exceptions import FileUploadError
from .models import FileDeleteResponse, FileListResponse, FileObject


logger = logging.getLogger(__name__)


class FileManager:
    """Manages file uploads, validation, and interaction with the Poe API."""

    def __init__(self):
        """Initializes the file manager."""
        self.files_db = {}

    @staticmethod
    @contextmanager
    def _temporary_file(contents: bytes, filename: str) -> Generator[str, None, None]:
        """Context manager for temporary file handling."""
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{filename}"
            ) as temp_file:
                temp_file.write(contents)
                temp_file_path = temp_file.name
            yield temp_file_path
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError as e:
                    logger.warning("Could not delete temp file %s: %s", temp_file_path, e)

    @staticmethod
    def validate_file(file: UploadFile):
        """Validates a file based on its name, size, and content type."""
        if not file.filename:
            raise FileUploadError("File must have a filename.", 400)

        max_size = MAX_FILE_SIZE_MB * 1024 * 1024
        if file.size and file.size > max_size:
            raise FileUploadError(
                f"File size exceeds {MAX_FILE_SIZE_MB}MB limit.", 413
            )

        if file.content_type not in ALLOWED_FILE_TYPES:
            raise FileUploadError(
                f"File type '{file.content_type}' not supported.", 415
            )


    @staticmethod
    async def upload_file_to_poe(file: UploadFile) -> fp.Attachment:
        """Uploads a file to Poe and returns the attachment."""
        FileManager.validate_file(file)

        try:
            contents = await file.read()
            with FileManager._temporary_file(
                contents, file.filename or "unknown"
            ) as temp_file_path:
                with open(temp_file_path, "rb") as f:
                    # Use async version for better performance in async context
                    attachment = await asyncio.to_thread(
                        fp.upload_file_sync, f, api_key=POE_API_KEY or ""
                    )

            logger.info("Successfully uploaded file %s to Poe", file.filename)
            return attachment

        except FileUploadError as e:
            logger.error("File validation failed for %s: %s", file.filename, e.message)
            raise
        except Exception as e:
            logger.error("Failed to upload file %s to Poe: %s", file.filename, e)
            raise FileUploadError(f"Failed to upload file: {e}", 500) from e

    @staticmethod
    async def process_files(files: Optional[List[UploadFile]]) -> List[fp.Attachment]:
        """Processes a list of uploaded files."""
        if not files:
            return []

        attachments = []
        for file in files:
            attachment = await FileManager.upload_file_to_poe(file)
            attachments.append(attachment)

        logger.info("Successfully processed %d files", len(attachments))
        return attachments

    async def list_files(self) -> FileListResponse:
        """Lists all uploaded files (in-memory)."""
        logger.info("Listing all files from in-memory database")
        files = list(self.files_db.values())
        return FileListResponse(data=files)

    async def get_file(self, file_id: str) -> FileObject:
        """Retrieves a file by its ID (in-memory)."""
        logger.info("Getting file %s from in-memory database", file_id)
        if file_id not in self.files_db:
            raise FileUploadError(f"File {file_id} not found", 404)
        return self.files_db[file_id]

    async def delete_file(self, file_id: str) -> FileDeleteResponse:
        """Deletes a file by its ID (in-memory)."""
        logger.info("Deleting file %s from in-memory database", file_id)
        if file_id not in self.files_db:
            raise FileUploadError(f"File {file_id} not found", 404)

        del self.files_db[file_id]
        return FileDeleteResponse(id=file_id, deleted=True)
