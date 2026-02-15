"""
Supabase Storage utility for criminal photos.
Handles upload, download, and listing of images in Supabase Storage.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
import hashlib

load_dotenv()

class SupabaseStorage:
    """Handles all Supabase Storage operations for criminal photos."""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY")
        self.bucket = os.getenv("SUPABASE_BUCKET", "criminal-photos")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        
        if self.key == "YOUR_SERVICE_ROLE_KEY_HERE":
            raise ValueError("Please replace SUPABASE_SERVICE_KEY with your actual service role key from Supabase Dashboard")
        
        self.client: Client = create_client(self.url, self.key)
        print(f"✓ Connected to Supabase Storage (bucket: {self.bucket})")
    
    def upload_image(
        self, 
        file_path: str, 
        criminal_id: int,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload an image to Supabase Storage.
        
        Args:
            file_path: Local path to the image file
            criminal_id: ID of the criminal this image belongs to
            filename: Optional custom filename (defaults to original)
            
        Returns:
            Dict with 'path', 'url', 'hash', and 'size' keys
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Image not found: {file_path}")
        
        # Read file and compute hash
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        
        # Determine storage path
        if filename is None:
            filename = file_path.name
        
        # Sanitize filename (remove spaces, special chars)
        safe_filename = "".join(c if c.isalnum() or c in '._-' else '_' for c in filename)
        storage_path = f"{criminal_id}/{safe_filename}"
        
        # Check if file already exists (by hash)
        existing = self._check_existing_hash(criminal_id, file_hash)
        if existing:
            print(f"  ℹ Image already exists in storage: {existing}")
            return {
                'path': existing,
                'url': self._get_public_url(existing),
                'hash': file_hash,
                'size': file_size,
                'already_existed': True
            }
        
        # Upload to Supabase Storage
        try:
            # Use upsert to overwrite if exists with same name
            result = self.client.storage.from_(self.bucket).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": self._get_content_type(file_path.suffix)}
            )
            
            public_url = self._get_public_url(storage_path)
            
            return {
                'path': storage_path,
                'url': public_url,
                'hash': file_hash,
                'size': file_size,
                'already_existed': False
            }
            
        except Exception as e:
            if "Duplicate" in str(e) or "already exists" in str(e).lower():
                # File exists, return existing URL
                public_url = self._get_public_url(storage_path)
                return {
                    'path': storage_path,
                    'url': public_url,
                    'hash': file_hash,
                    'size': file_size,
                    'already_existed': True
                }
            raise Exception(f"Failed to upload image: {str(e)}")
    
    def upload_bytes(
        self,
        file_bytes: bytes,
        criminal_id: int,
        filename: str
    ) -> Dict[str, Any]:
        """
        Upload image bytes directly to Supabase Storage.
        
        Args:
            file_bytes: Raw image bytes
            criminal_id: ID of the criminal
            filename: Filename with extension
            
        Returns:
            Dict with upload details
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        
        # Sanitize filename
        safe_filename = "".join(c if c.isalnum() or c in '._-' else '_' for c in filename)
        storage_path = f"{criminal_id}/{safe_filename}"
        
        # Get content type from extension
        ext = Path(filename).suffix.lower()
        content_type = self._get_content_type(ext)
        
        try:
            self.client.storage.from_(self.bucket).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type}
            )
            
            return {
                'path': storage_path,
                'url': self._get_public_url(storage_path),
                'hash': file_hash,
                'size': file_size
            }
        except Exception as e:
            if "Duplicate" in str(e) or "already exists" in str(e).lower():
                return {
                    'path': storage_path,
                    'url': self._get_public_url(storage_path),
                    'hash': file_hash,
                    'size': file_size,
                    'already_existed': True
                }
            raise
    
    def download_image(self, storage_path: str) -> bytes:
        """
        Download an image from Supabase Storage.
        
        Args:
            storage_path: Path in storage (e.g., "123/photo.jpg")
            
        Returns:
            Raw image bytes
        """
        try:
            response = self.client.storage.from_(self.bucket).download(storage_path)
            return response
        except Exception as e:
            raise Exception(f"Failed to download image: {str(e)}")
    
    def list_criminal_images(self, criminal_id: int) -> List[Dict[str, Any]]:
        """
        List all images for a specific criminal.
        
        Args:
            criminal_id: ID of the criminal
            
        Returns:
            List of file metadata dicts
        """
        try:
            files = self.client.storage.from_(self.bucket).list(str(criminal_id))
            return [
                {
                    'name': f['name'],
                    'path': f"{criminal_id}/{f['name']}",
                    'url': self._get_public_url(f"{criminal_id}/{f['name']}"),
                    'size': f.get('metadata', {}).get('size', 0),
                    'created_at': f.get('created_at')
                }
                for f in files if f['name']  # Filter out empty entries
            ]
        except Exception as e:
            print(f"Warning: Could not list images for criminal {criminal_id}: {e}")
            return []
    
    def delete_image(self, storage_path: str) -> bool:
        """
        Delete an image from Supabase Storage.
        
        Args:
            storage_path: Path in storage
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.storage.from_(self.bucket).remove([storage_path])
            return True
        except Exception as e:
            print(f"Warning: Could not delete {storage_path}: {e}")
            return False
    
    def _get_public_url(self, storage_path: str) -> str:
        """Get the public URL for a stored file."""
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{storage_path}"
    
    def _get_content_type(self, extension: str) -> str:
        """Get MIME type from file extension."""
        ext = extension.lower().lstrip('.')
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def _check_existing_hash(self, criminal_id: int, file_hash: str) -> Optional[str]:
        """
        Check if a file with the same hash already exists.
        This would require storing hashes in the database - for now, return None.
        """
        # TODO: Implement hash checking via database query
        return None


# Singleton instance
_storage_instance: Optional[SupabaseStorage] = None

def get_storage() -> SupabaseStorage:
    """Get or create the Supabase Storage singleton."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = SupabaseStorage()
    return _storage_instance


if __name__ == "__main__":
    # Test connection
    try:
        storage = get_storage()
        print("✓ Supabase Storage connection successful!")
        
        # Test listing (will be empty if bucket is new)
        print("\nTesting bucket access...")
        # This will fail if bucket doesn't exist
        try:
            files = storage.client.storage.from_(storage.bucket).list("")
            print(f"✓ Bucket '{storage.bucket}' accessible ({len(files)} top-level items)")
        except Exception as e:
            print(f"✗ Bucket '{storage.bucket}' not found or not accessible")
            print(f"  Please create the bucket in Supabase Dashboard: Storage → New Bucket")
            print(f"  Error: {e}")
            
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
