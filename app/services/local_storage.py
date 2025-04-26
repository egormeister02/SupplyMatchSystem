import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from app.config.logging import app_logger

class LocalStorageService:
    """Local file storage service"""
    
    def __init__(self, storage_path="storage"):
        """
        Initialize local storage service
        
        Args:
            storage_path (str): Path to storage directory
        """
        self.storage_path = storage_path
        self._ensure_storage_exists()
        app_logger.info(f"Local storage initialized. Path: {self.storage_path}")
    
    def _ensure_storage_exists(self):
        """Check and create storage directory if it doesn't exist"""
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
            app_logger.info(f"Created storage directory: {self.storage_path}")
    
    def _generate_file_path(self, file_name):
        """
        Generate unique path for saving file
        
        Args:
            file_name (str): Original file name
        
        Returns:
            str: Relative path for saved file
        """
        # Create date-based directory structure
        today = datetime.now().strftime("%Y/%m/%d")
        
        # Generate unique filename
        file_extension = os.path.splitext(file_name)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        
        # Final relative path
        relative_path = os.path.join(today, unique_filename)
        
        # Create necessary subdirectories
        abs_dir_path = os.path.join(self.storage_path, today)
        os.makedirs(abs_dir_path, exist_ok=True)
        
        return relative_path
    
    async def save_file(self, file_path, original_name=None):
        """
        Save file to local storage
        
        Args:
            file_path (str): Path to temporary file
            original_name (str, optional): Original filename
        
        Returns:
            str: Relative path to saved file
        """
        if original_name is None:
            original_name = os.path.basename(file_path)
            
        # Generate storage path
        storage_relative_path = self._generate_file_path(original_name)
        storage_full_path = os.path.join(self.storage_path, storage_relative_path)
        
        # Copy file to storage
        try:
            shutil.copy2(file_path, storage_full_path)
            app_logger.info(f"File saved: {storage_relative_path}")
            return storage_relative_path
        except Exception as e:
            app_logger.error(f"Error saving file: {str(e)}")
            raise
    
    async def get_file_path(self, file_path):
        """
        Get full path to file
        
        Args:
            file_path (str): Relative path to file
        
        Returns:
            str: Full path to file
        """
        full_path = os.path.join(self.storage_path, file_path)
        if not os.path.exists(full_path):
            app_logger.error(f"File not found: {full_path}")
            return None
        return full_path
    
    async def delete_file(self, file_path):
        """
        Delete file from storage
        
        Args:
            file_path (str): Relative path to file
        
        Returns:
            bool: True if file was deleted successfully, False otherwise
        """
        full_path = os.path.join(self.storage_path, file_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                app_logger.info(f"File deleted: {file_path}")
                return True
            else:
                app_logger.warning(f"File not found for deletion: {file_path}")
                return False
        except Exception as e:
            app_logger.error(f"Error deleting file: {str(e)}")
            return False

# Create service instance
local_storage_service = LocalStorageService() 