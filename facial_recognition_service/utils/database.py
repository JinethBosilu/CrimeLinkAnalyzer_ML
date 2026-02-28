"""
Database utility for facial recognition service.
Connects to Supabase PostgreSQL (same database as Spring Boot backend).
"""

import os
import json
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

class Database:
    """Handles all database operations for the facial recognition service."""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        
        if not self.database_url:
            raise ValueError("DATABASE_URL must be set in .env")
        
        # Test connection
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            print("✓ Connected to Supabase PostgreSQL")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def ensure_tables_exist(self):
        """
        Ensure required tables exist for facial recognition.
        This adds columns to the existing criminals table and creates suspect_photos table.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Add face_embedding column to criminals if it doesn't exist
                cur.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'criminals' AND column_name = 'face_embedding'
                        ) THEN
                            ALTER TABLE criminals ADD COLUMN face_embedding JSONB;
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'criminals' AND column_name = 'risk_level'
                        ) THEN
                            ALTER TABLE criminals ADD COLUMN risk_level VARCHAR(50) DEFAULT 'medium';
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'criminals' AND column_name = 'crime_history'
                        ) THEN
                            ALTER TABLE criminals ADD COLUMN crime_history TEXT;
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'criminals' AND column_name = 'primary_photo_url'
                        ) THEN
                            ALTER TABLE criminals ADD COLUMN primary_photo_url VARCHAR(500);
                        END IF;
                    END $$;
                """)
                
                # Create suspect_photos table if not exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS suspect_photos (
                        photo_id SERIAL PRIMARY KEY,
                        criminal_id VARCHAR(100) REFERENCES criminals(id) ON DELETE CASCADE,
                        photo_url VARCHAR(500) NOT NULL,
                        photo_hash VARCHAR(64),
                        embedding JSONB,
                        face_confidence FLOAT,
                        face_bbox JSONB,
                        photo_quality FLOAT,
                        image_width INT,
                        image_height INT,
                        file_size_bytes INT,
                        is_primary BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(photo_hash)
                    );
                """)
                
                # Create index for criminal lookups (skip embedding index - we'll do sequential scan)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_criminals_nic ON criminals (nic);
                """)
                
                print("✓ Database tables verified/created")
    
    def get_criminal_by_id(self, criminal_id: str) -> Optional[Dict[str, Any]]:
        """Get a criminal record by ID."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM criminals WHERE id = %s",
                    (criminal_id,)
                )
                return cur.fetchone()
    
    def get_criminal_by_nic(self, nic: str) -> Optional[Dict[str, Any]]:
        """Get a criminal record by NIC."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM criminals WHERE nic = %s",
                    (nic,)
                )
                return cur.fetchone()
    
    def create_criminal(
        self,
        name: str,
        nic: str,
        crime_history: Optional[str] = None,
        risk_level: str = 'medium',
        address: Optional[str] = None,
        contact_number: Optional[str] = None,
        secondary_contact: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        alias: Optional[str] = None,
        status: str = 'active'
    ) -> str:
        """
        Create a new criminal record.
        
        Returns:
            The ID of the created criminal
        """
        import uuid
        criminal_id = str(uuid.uuid4())[:8]  # Short UUID for readability
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO criminals (
                        id, name, nic, crime_history, risk_level, address,
                        contact_number, secondary_contact, date_of_birth, gender, alias, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    criminal_id, name, nic, crime_history, risk_level, address,
                    contact_number, secondary_contact, date_of_birth, gender, alias, status
                ))
                result = cur.fetchone()
                return result['id']
    
    def update_criminal_embedding(
        self,
        criminal_id: str,
        embedding: List[float],
        primary_photo_url: Optional[str] = None
    ):
        """Update the face embedding for a criminal."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if primary_photo_url:
                    cur.execute("""
                        UPDATE criminals 
                        SET face_embedding = %s, primary_photo_url = %s
                        WHERE id = %s
                    """, (json.dumps(embedding), primary_photo_url, criminal_id))
                else:
                    cur.execute("""
                        UPDATE criminals 
                        SET face_embedding = %s
                        WHERE id = %s
                    """, (json.dumps(embedding), criminal_id))
    
    def store_suspect_photo(
        self,
        criminal_id: str,
        photo_url: str,
        photo_hash: str,
        embedding: List[float],
        face_confidence: float = 0.0,
        face_bbox: Optional[Dict] = None,
        photo_quality: float = 0.0,
        image_width: int = 0,
        image_height: int = 0,
        file_size_bytes: int = 0,
        is_primary: bool = False
    ) -> int:
        """
        Store a suspect photo record.
        
        Returns:
            The photo_id of the created record
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Check if hash already exists
                cur.execute("SELECT photo_id FROM suspect_photos WHERE photo_hash = %s", (photo_hash,))
                existing = cur.fetchone()
                if existing:
                    return existing['photo_id']
                
                cur.execute("""
                    INSERT INTO suspect_photos 
                    (criminal_id, photo_url, photo_hash, embedding, face_confidence, face_bbox,
                     photo_quality, image_width, image_height, file_size_bytes, is_primary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING photo_id
                """, (
                    criminal_id, photo_url, photo_hash, json.dumps(embedding),
                    face_confidence, json.dumps(face_bbox) if face_bbox else None,
                    photo_quality, image_width, image_height, file_size_bytes, is_primary
                ))
                result = cur.fetchone()
                return result['photo_id']
    
    def get_all_criminals_with_embeddings(self) -> List[Dict[str, Any]]:
        """Get all criminals that have face embeddings stored."""
        import numpy as np
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, nic, crime_history, risk_level, face_embedding, primary_photo_url, status
                    FROM criminals 
                    WHERE face_embedding IS NOT NULL
                """)
                results = cur.fetchall()
                
                # Parse embeddings - handle both BYTEA (binary) and JSONB formats
                for row in results:
                    if row['face_embedding']:
                        embedding_data = row['face_embedding']
                        
                        # Handle memoryview/bytes (BYTEA format - numpy array bytes)
                        if isinstance(embedding_data, (memoryview, bytes)):
                            raw_bytes = bytes(embedding_data)
                            row['face_embedding'] = np.frombuffer(raw_bytes, dtype=np.float32).tolist()
                        # Handle string (JSON format)
                        elif isinstance(embedding_data, str):
                            row['face_embedding'] = json.loads(embedding_data)
                        # Handle list (already parsed JSONB)
                        elif isinstance(embedding_data, list):
                            pass  # Already in correct format
                
                return results
    
    def get_criminal_photos(self, criminal_id: str) -> List[Dict[str, Any]]:
        """Get all photos for a specific criminal."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM suspect_photos 
                    WHERE criminal_id = %s
                    ORDER BY is_primary DESC, created_at DESC
                """, (criminal_id,))
                return cur.fetchall()
    
    def get_all_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get all criminals with embeddings in format ready for face matching.
        
        Returns:
            List of dicts with 'criminal_id', 'name', 'nic', 'embedding', 'photo_url', 'risk_level', 'crime_history'
        """
        criminals = self.get_all_criminals_with_embeddings()
        result = []
        
        for c in criminals:
            embedding = c.get('face_embedding')
            if embedding:
                import numpy as np
                result.append({
                    'criminal_id': c['id'],
                    'name': c.get('name', 'Unknown'),
                    'nic': c.get('nic', ''),
                    'embedding': np.array(embedding, dtype=np.float32),
                    'photo_url': c.get('primary_photo_url'),
                    'risk_level': c.get('risk_level'),
                    'crime_history': c.get('crime_history'),
                })
        
        return result
    
    def get_criminal_details(self, criminal_id: str) -> Optional[Dict[str, Any]]:
        """Get full details for a specific criminal."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM criminals WHERE id = %s", (str(criminal_id),))
                return cur.fetchone()
    
    def get_all_criminals(self) -> List[Dict[str, Any]]:
        """Get all criminals."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, nic, crime_history, risk_level, primary_photo_url, status
                    FROM criminals 
                    ORDER BY name
                """)
                return cur.fetchall()
    
    def ensure_audit_table_exists(self):
        """Create facial recognition audit log table if it doesn't exist."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS facial_recognition_logs (
                        log_id SERIAL PRIMARY KEY,
                        uploaded_image_url VARCHAR(500),
                        uploaded_image_hash VARCHAR(64),
                        face_detected BOOLEAN DEFAULT FALSE,
                        face_count INT DEFAULT 0,
                        face_quality VARCHAR(20),
                        matches_found INT DEFAULT 0,
                        best_match_criminal_id VARCHAR(100),
                        best_match_similarity FLOAT,
                        all_matches JSONB,
                        processing_time_ms INT,
                        requested_by VARCHAR(100),
                        user_role VARCHAR(50),
                        ip_address VARCHAR(45),
                        case_id VARCHAR(100),
                        model_version VARCHAR(50) DEFAULT 'buffalo_sc',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                print("✓ Audit log table verified/created")
    
    def log_recognition_request(
        self,
        uploaded_image_url: str,
        uploaded_image_hash: str,
        face_detected: bool,
        face_count: int,
        face_quality: str,
        matches_found: int,
        best_match_criminal_id: Optional[str],
        best_match_similarity: float,
        all_matches: List[Dict],
        processing_time_ms: int,
        requested_by: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        case_id: Optional[str] = None,
        match_threshold: float = 0.45
    ) -> int:
        """
        Log a facial recognition request for audit purposes.
        
        Returns:
            The log_id of the created record
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Convert user_id to integer if possible, otherwise None
                user_id_int = None
                if requested_by and requested_by not in ('unknown', 'null', ''):
                    try:
                        user_id_int = int(requested_by)
                    except (ValueError, TypeError):
                        user_id_int = None
                
                # Convert criminal_id to integer if possible
                criminal_id_int = None
                if best_match_criminal_id:
                    try:
                        criminal_id_int = int(best_match_criminal_id)
                    except (ValueError, TypeError):
                        criminal_id_int = None
                
                cur.execute("""
                    INSERT INTO facial_recognition_logs 
                    (analysis_type, uploaded_image_url, uploaded_image_hash, face_detected, face_count, 
                     face_quality, matches_found, best_match_criminal_id, best_match_similarity, 
                     match_threshold, all_matches, processing_time_ms, model_version, 
                     requested_by, user_role, case_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING log_id
                """, (
                    'face_recognition',  # analysis_type
                    uploaded_image_url, 
                    uploaded_image_hash, 
                    face_detected, 
                    face_count, 
                    face_quality,
                    matches_found, 
                    criminal_id_int,  # best_match_criminal_id as integer
                    best_match_similarity,
                    match_threshold,  # match_threshold
                    json.dumps(all_matches), 
                    processing_time_ms, 
                    'buffalo_sc',  # model_version
                    user_id_int,  # requested_by as integer
                    user_role,
                    case_id
                ))
                result = cur.fetchone()
                return result['log_id']
    
    def get_recognition_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent facial recognition logs."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("""
                        SELECT * FROM facial_recognition_logs 
                        WHERE requested_by = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (user_id, limit))
                else:
                    cur.execute("""
                        SELECT * FROM facial_recognition_logs 
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                return cur.fetchall()


# Singleton instance
_db_instance: Optional[Database] = None

def get_database() -> Database:
    """Get or create the Database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.ensure_tables_exist()
    return _db_instance


if __name__ == "__main__":
    # Test connection
    try:
        db = get_database()
        print("\n✓ Database connection and setup successful!")
        
        # Test query
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as count FROM criminals")
                result = cur.fetchone()
                print(f"✓ Found {result['count']} criminals in database")
                
    except Exception as e:
        print(f"✗ Database error: {e}")
