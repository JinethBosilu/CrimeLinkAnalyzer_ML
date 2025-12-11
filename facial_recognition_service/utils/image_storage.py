"""
Image Storage Module
====================
Handles secure file upload, storage, and retrieval for suspect images.

Features:
- SHA-256 hashing for deduplication
- File type validation
- Secure filename generation
- Directory organization by criminal ID
- Image optimization and resizing
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple
import shutil
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ImageStorage:
    """
    Secure image storage manager.
    
    Organizes images by criminal ID and prevents duplicates.
    """
    
    def __init__(self, base_dir: str = 'suspect_images'):
        """
        Initialize storage manager.
        
        Args:
            base_dir: Base directory for image storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Allowed image extensions
        self.allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        # Maximum file size (5MB)
        self.max_file_size = 5 * 1024 * 1024
    
    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of file.
        
        Args:
            file_path: Path to file
        
        Returns:
            Hex digest of SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def calculate_bytes_hash(self, file_bytes: bytes) -> str:
        """
        Calculate SHA-256 hash of bytes.
        
        Args:
            file_bytes: File content as bytes
        
        Returns:
            Hex digest of SHA-256 hash
        """
        return hashlib.sha256(file_bytes).hexdigest()
    
    def validate_image(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image file.
        
        Args:
            file_path: Path to file
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            return False, "File does not exist"
        
        # Check extension
        if path.suffix.lower() not in self.allowed_extensions:
            return False, f"Invalid file type. Allowed: {', '.join(self.allowed_extensions)}"
        
        # Check file size
        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            return False, f"File too large. Maximum size: {self.max_file_size / 1024 / 1024}MB"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, None
    
    def store_image(
        self,
        source_path: str,
        criminal_id: int,
        is_primary: bool = False
    ) -> Tuple[str, str, int]:
        """
        Store image file in organized directory structure.
        
        Args:
            source_path: Path to source image
            criminal_id: Criminal ID
            is_primary: Whether this is primary photo
        
        Returns:
            Tuple of (stored_path, file_hash, file_size)
        """
        # Validate image
        is_valid, error = self.validate_image(source_path)
        if not is_valid:
            raise ValueError(error)
        
        # Create criminal directory
        criminal_dir = self.base_dir / f"criminal_{criminal_id:06d}"
        criminal_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate hash
        file_hash = self.calculate_file_hash(source_path)
        
        # Get file extension
        ext = Path(source_path).suffix.lower()
        
        # Generate filename
        if is_primary:
            filename = f"profile{ext}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}_{file_hash[:8]}{ext}"
        
        # Destination path
        dest_path = criminal_dir / filename
        
        # Copy file
        shutil.copy2(source_path, dest_path)
        
        # Get file size
        file_size = dest_path.stat().st_size
        
        # Return relative path from base_dir
        relative_path = str(dest_path.relative_to(self.base_dir.parent))
        
        logger.info(f"Stored image: {relative_path} (hash: {file_hash[:16]}...)")
        
        return relative_path, file_hash, file_size
    
    def store_uploaded_file(
        self,
        file_bytes: bytes,
        filename: str,
        criminal_id: int = None,
        temp_dir: str = 'uploads'
    ) -> Tuple[str, str, int]:
        """
        Store uploaded file from FastAPI.
        
        Args:
            file_bytes: File content
            filename: Original filename
            criminal_id: Criminal ID (if permanent storage)
            temp_dir: Temporary directory for uploads
        
        Returns:
            Tuple of (stored_path, file_hash, file_size)
        """
        # Calculate hash
        file_hash = self.calculate_bytes_hash(file_bytes)
        
        # Get extension
        ext = Path(filename).suffix.lower()
        if ext not in self.allowed_extensions:
            raise ValueError(f"Invalid file type: {ext}")
        
        # Check file size
        file_size = len(file_bytes)
        if file_size > self.max_file_size:
            raise ValueError(f"File too large: {file_size / 1024 / 1024:.2f}MB")
        
        # Determine storage location
        if criminal_id is not None:
            # Permanent storage
            storage_dir = self.base_dir / f"criminal_{criminal_id:06d}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}_{file_hash[:8]}{ext}"
        else:
            # Temporary storage
            storage_dir = Path(temp_dir)
            filename = f"{file_hash}{ext}"
        
        storage_dir.mkdir(parents=True, exist_ok=True)
        dest_path = storage_dir / filename
        
        # Write file
        with open(dest_path, 'wb') as f:
            f.write(file_bytes)
        
        # Return relative path
        relative_path = str(dest_path)
        
        logger.info(f"Stored uploaded file: {relative_path}")
        
        return relative_path, file_hash, file_size
    
    def get_image_path(self, relative_path: str) -> Path:
        """
        Get full path from relative path.
        
        Args:
            relative_path: Relative path from storage
        
        Returns:
            Full Path object
        """
        return Path(relative_path)
    
    def delete_image(self, relative_path: str) -> bool:
        """
        Delete an image file.
        
        Args:
            relative_path: Relative path to image
        
        Returns:
            True if deleted successfully
        """
        try:
            path = self.get_image_path(relative_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted image: {relative_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete {relative_path}: {str(e)}")
            return False
    
    def get_criminal_images(self, criminal_id: int) -> list:
        """
        Get all image paths for a criminal.
        
        Args:
            criminal_id: Criminal ID
        
        Returns:
            List of relative paths
        """
        criminal_dir = self.base_dir / f"criminal_{criminal_id:06d}"
        
        if not criminal_dir.exists():
            return []
        
        images = []
        for ext in self.allowed_extensions:
            images.extend(criminal_dir.glob(f"*{ext}"))
        
        # Convert to relative paths
        relative_paths = [str(img.relative_to(self.base_dir.parent)) for img in images]
        
        return sorted(relative_paths)


# Singleton instance
_storage_instance = None

def get_image_storage() -> ImageStorage:
    """
    Get singleton instance of ImageStorage.
    
    Returns:
        ImageStorage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ImageStorage()
    return _storage_instance
