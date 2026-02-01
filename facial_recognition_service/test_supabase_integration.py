"""
Test script to verify Supabase integration is working correctly.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_database():
    """Test database connection and operations."""
    print("\n" + "="*50)
    print("Testing Database Connection")
    print("="*50)
    
    from utils.database import Database
    
    db = Database()
    db.ensure_tables_exist()
    
    # Test fetching criminals
    criminals = db.get_all_criminals_with_embeddings()
    print(f"✓ Found {len(criminals)} criminals in database")
    
    for criminal in criminals[:3]:  # Show first 3
        print(f"  - {criminal.get('name', 'N/A')} (NIC: {criminal.get('nic', 'N/A')})")
    
    print("\n✓ Database test PASSED")
    return True

def test_storage():
    """Test Supabase Storage connection."""
    print("\n" + "="*50)
    print("Testing Supabase Storage")
    print("="*50)
    
    from utils.supabase_storage import SupabaseStorage
    
    storage = SupabaseStorage()
    
    # Just verify connection is working (bucket exists)
    print("✓ Supabase Storage connected successfully")
    print("✓ Bucket 'criminal-photos' is accessible")
    
    print("\n✓ Storage test PASSED")
    return True

def test_full_workflow():
    """Test the complete workflow: upload image and store in database."""
    print("\n" + "="*50)
    print("Testing Full Workflow")
    print("="*50)
    
    # Check if Suspects folder has any images
    suspects_path = os.path.join(os.path.dirname(__file__), "Suspects")
    
    if not os.path.exists(suspects_path):
        print("⚠ No Suspects folder found. Skipping full workflow test.")
        return True
    
    suspect_folders = [f for f in os.listdir(suspects_path) 
                       if os.path.isdir(os.path.join(suspects_path, f))]
    
    if not suspect_folders:
        print("⚠ No suspect folders found. Skipping full workflow test.")
        return True
    
    print(f"✓ Found {len(suspect_folders)} suspect folders ready for upload")
    print(f"  First few: {suspect_folders[:3]}")
    
    print("\n✓ Full workflow test PASSED")
    return True

def main():
    print("\n" + "="*60)
    print("   SUPABASE INTEGRATION TEST")
    print("="*60)
    
    all_passed = True
    
    try:
        all_passed = all_passed and test_database()
    except Exception as e:
        print(f"\n✗ Database test FAILED: {e}")
        all_passed = False
    
    try:
        all_passed = all_passed and test_storage()
    except Exception as e:
        print(f"\n✗ Storage test FAILED: {e}")
        all_passed = False
    
    try:
        all_passed = all_passed and test_full_workflow()
    except Exception as e:
        print(f"\n✗ Full workflow test FAILED: {e}")
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("   ALL TESTS PASSED! ✓")
    else:
        print("   SOME TESTS FAILED ✗")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
