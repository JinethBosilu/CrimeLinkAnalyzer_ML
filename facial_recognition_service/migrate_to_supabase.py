"""
Simple migration script to upload existing local criminal images to Supabase Storage.
This uploads images without processing face embeddings.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from utils.supabase_storage import SupabaseStorage
from utils.database import Database

def migrate_to_supabase():
    """Migrate local stored_images to Supabase Storage."""
    print("=" * 60)
    print("Migration: Local Images → Supabase Storage")
    print("=" * 60)
    
    # Initialize
    storage = SupabaseStorage()
    db = Database()
    db.ensure_tables_exist()
    
    # Find stored_images folder
    stored_images = Path(__file__).parent / "stored_images"
    
    if not stored_images.exists():
        print(f"✗ stored_images folder not found: {stored_images}")
        return
    
    # Get criminal folders
    criminal_folders = [f for f in stored_images.iterdir() if f.is_dir()]
    print(f"\nFound {len(criminal_folders)} criminal folders to migrate")
    print()
    
    success_count = 0
    
    for folder in criminal_folders:
        criminal_id = folder.name  # e.g., "criminal_2"
        print(f"Processing: {criminal_id}")
        
        # Find images in this folder
        images = list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png"))
        
        if not images:
            print(f"  ⚠ No images found in {folder.name}")
            continue
        
        for img_path in images:
            try:
                # Upload to Supabase Storage
                result = storage.upload_image(
                    file_path=str(img_path),
                    criminal_id=criminal_id,
                    filename=img_path.name
                )
                
                if result:
                    print(f"  ✓ Uploaded: {img_path.name}")
                    print(f"    URL: {result['url']}")
                    success_count += 1
                else:
                    print(f"  ✗ Failed to upload: {img_path.name}")
                    
            except Exception as e:
                print(f"  ✗ Error uploading {img_path.name}: {e}")
    
    print()
    print("=" * 60)
    print(f"Migration Complete!")
    print(f"  Uploaded: {success_count} images")
    print("=" * 60)

if __name__ == "__main__":
    migrate_to_supabase()
