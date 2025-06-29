"""
Handles file uploads, validation, and interaction with the Poe API.
"""

import asyncio
import logging
import os
import tempfile
import time
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

        # FastAPI's UploadFile does NOT expose a .size attribute by default.
        # We attempt to determine size safely; if not available, we skip the check.
        file_size = getattr(file, "size", None)
        if file_size is None:
            try:
                current_pos = awaitable_seek_pos = None
            except Exception:
                pass
        if file_size is None:
            try:
                current_pos = file.file.tell()
                file.file.seek(0, os.SEEK_END)
                file_size = file.file.tell()
                file.file.seek(current_pos)
            except Exception:
                file_size = None

        if file_size and file_size > max_size:
            raise FileUploadError(
                f"File size exceeds {MAX_FILE_SIZE_MB}MB limit.", 413
            )

        content_type = getattr(file, "content_type", None)
        if content_type and content_type not in ALLOWED_FILE_TYPES:
            raise FileUploadError(
                f"File type '{content_type}' not supported.", 415
            )

    @staticmethod
    async def upload_file_to_poe(file: UploadFile) -> fp.Attachment:
        """Uploads a file to Poe and returns the attachment."""
        FileManager.validate_file(file)

        try:
            contents = await file.read()
            
            # Create a temporary file to match Poe's documentation pattern
            with FileManager._temporary_file(
                contents, file.filename or "unknown"
            ) as temp_file_path:
                # Open file and upload as shown in Poe docs
                with open(temp_file_path, "rb") as f:
                    attachment = await asyncio.to_thread(
                        fp.upload_file_sync, 
                        f, 
                        api_key=POE_API_KEY
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
    async def upload_local_file_to_poe(file_path: str) -> fp.Attachment:
        """Uploads a local file to Poe and returns the attachment."""
        try:
            # Open file and upload as shown in Poe docs
            with open(file_path, "rb") as f:
                attachment = await asyncio.to_thread(
                    fp.upload_file_sync,
                    f,
                    api_key=POE_API_KEY
                )
            
            logger.info("Successfully uploaded local file %s to Poe", file_path)
            return attachment
            
        except Exception as e:
            logger.error("Failed to upload local file %s to Poe: %s", file_path, e)
            raise FileUploadError(f"Failed to upload file: {e}", 500) from e

    async def process_files(self, files: Optional[List[UploadFile]]) -> List[fp.Attachment]:
        """Processes a list of uploaded files and returns Poe attachments."""
        if not files:
            logger.info("No files to process")
            return []

        logger.info("Processing %d files for upload", len(files))
        attachments = []
        
        for i, file in enumerate(files):
            logger.info("Processing file %d: %s (size: %s, content_type: %s)", 
                       i + 1, file.filename, getattr(file, 'size', 'unknown'), 
                       getattr(file, 'content_type', 'unknown'))
            
            # Upload file to Poe and get attachment
            attachment = await FileManager.upload_file_to_poe(file)
            attachments.append(attachment)
            
            logger.info("File %s uploaded successfully, attachment: %s", 
                       file.filename, attachment)
            
            # Store file metadata in memory database for tracking
            file_id = f"file_{len(self.files_db)}_{int(time.time())}"
            file_obj = FileObject(
                id=file_id,
                object="file",
                bytes=getattr(file, 'size', 0) or 0,
                created_at=int(time.time()),
                filename=file.filename or "unknown",
                purpose="assistants"
            )
            self.files_db[file_obj.id] = file_obj

        logger.info("Successfully processed %d files for Poe, attachments: %s", 
                   len(attachments), attachments)
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