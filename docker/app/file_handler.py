import tempfile
import os
from typing import List, Optional
from fastapi import UploadFile
import fastapi_poe as fp
from .config import POE_API_KEY, MAX_FILE_SIZE_MB, ALLOWED_FILE_TYPES
from .exceptions import FileUploadError
from .models import FileObject, FileListResponse, FileDeleteResponse
import logging

logger = logging.getLogger(__name__)


class FileManager:
    def __init__(self):
        # Simple in-memory file storage for demo purposes
        # In production, you'd use a database
        self.files_db = {}
    
    @staticmethod
    def validate_file(file: UploadFile) -> None:
        if not file.filename:
            raise FileUploadError("File must have a filename", 400)
            
        max_size = MAX_FILE_SIZE_MB * 1024 * 1024
        if file.size and file.size > max_size:
            raise FileUploadError(f"File size exceeds {MAX_FILE_SIZE_MB}MB limit", 413)
        
        if file.content_type not in ALLOWED_FILE_TYPES:
            raise FileUploadError(f"File type {file.content_type} not supported. Allowed types: {ALLOWED_FILE_TYPES}", 415)

    @staticmethod
    async def upload_file_to_poe(file: UploadFile) -> fp.Attachment:
        FileManager.validate_file(file)
        
        temp_file_path = None
        try:
            contents = await file.read()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
                temp_file.write(contents)
                temp_file_path = temp_file.name
            
            with open(temp_file_path, "rb") as f:
                attachment = fp.upload_file_sync(f, api_key=POE_API_KEY or "")
            
            logger.info(f"Successfully uploaded file {file.filename} to Poe")
            return attachment
            
        except FileUploadError:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file {file.filename} to Poe: {e}")
            raise FileUploadError(f"Failed to upload file: {str(e)}", 500)
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError as e:
                    logger.warning(f"Could not delete temp file {temp_file_path}: {e}")

    @staticmethod
    async def process_files(files: Optional[List[UploadFile]]) -> List[fp.Attachment]:
        if not files:
            return []
        
        attachments = []
        for file in files:
            try:
                attachment = await FileManager.upload_file_to_poe(file)
                attachments.append(attachment)
            except FileUploadError as e:
                logger.error(f"Failed to process file {file.filename}: {e.message}")
                raise e
        
        logger.info(f"Successfully processed {len(attachments)} files")
        return attachments

    async def list_files(self) -> FileListResponse:
        """List all uploaded files"""
        # WARNING: Files are uploaded to Poe but not tracked locally
        # This will return empty list as files_db is not populated
        logger.info("Listing all files")
        files = list(self.files_db.values())
        return FileListResponse(data=files)

    async def get_file(self, file_id: str) -> FileObject:
        """Get a specific file by ID"""
        logger.info(f"Getting file {file_id}")
        if file_id not in self.files_db:
            raise FileUploadError(f"File {file_id} not found", 404)
        return self.files_db[file_id]

    async def delete_file(self, file_id: str) -> FileDeleteResponse:
        """Delete a file by ID"""
        logger.info(f"Deleting file {file_id}")
        if file_id not in self.files_db:
            raise FileUploadError(f"File {file_id} not found", 404)
        
        del self.files_db[file_id]
        return FileDeleteResponse(
            id=file_id,
            deleted=True
        )