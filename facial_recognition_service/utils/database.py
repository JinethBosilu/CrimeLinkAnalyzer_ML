"""
Database Module for Facial Recognition
=======================================
PostgreSQL database operations for storing and retrieving face embeddings.

Features:
- Secure connection management using connection pooling
- Efficient embedding storage and retrieval
- Transaction support with proper error handling
- Prepared statements to prevent SQL injection
"""

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import numpy as np
from typing import List, Dict, Optional, Tuple
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FacialRecognitionDB:
    """
    Database operations for facial recognition system.
    
    Uses connection pooling for better performance and resource management.
    """
    
    def __init__(self):
        """Initialize database connection pool."""
        # Get database credentials from environment
        self.db_url = os.getenv(
            'DB_URL',
            'postgresql://postgres:BtGAnoXbRJzmmXjXMrlMnqoqLoAAIlgT@centerbeam.proxy.rlwy.net:23821/railway'
        )
        
        # Create connection pool (min 2, max 10 connections)
        try:
            self.pool = ConnectionPool(
                self.db_url,
                min_size=2,
                max_size=10,
                kwargs={'row_factory': dict_row}
            )
            logger.info("✓ Database connection pool created")
        except Exception as e:
            logger.error(f"✗ Failed to create connection pool: {str(e)}")
            raise
    
    def _get_connection(self):
        """Get connection from pool (context manager)."""
        return self.pool.connection()
    
    # ========================================================================
    # CRIMINAL OPERATIONS
    # ========================================================================
    
    def create_criminal(
        self,
        name: str,
        nic: str = None,
        date_of_birth: str = None,
        gender: str = None,
        address: str = None,
        crime_history: dict = None,
        risk_level: str = 'medium',
        created_by: int = None,
        notes: str = None
    ) -> int:
        """
        Create a new criminal record.
        
        Args:
            name: Full name
            nic: National Identity Card number
            date_of_birth: Date of birth (YYYY-MM-DD) - optional
            gender: Gender (Male/Female/Other) - optional
            address: Address - optional
            crime_history: Crime history dict - optional
            risk_level: Risk level (low/medium/high/critical)
            created_by: User ID who created this record
            notes: Additional notes
        
        Returns:
            criminal_id: ID of newly created criminal
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    INSERT INTO criminals (
                        name, nic, date_of_birth, gender, address,
                        crime_history, risk_level, created_by, notes, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active'
                    )
                    RETURNING criminal_id
                """
                
                crime_history_json = json.dumps(crime_history or {})
                
                cur.execute(query, (
                    name, nic, date_of_birth, gender, address,
                    crime_history_json, risk_level, created_by, notes
                ))
                
                result = cur.fetchone()
                conn.commit()
                
                criminal_id = result['criminal_id']
                logger.info(f"Created criminal record: ID={criminal_id}, Name={name}")
                return criminal_id
    
    def store_criminal_embedding(
        self,
        criminal_id: int,
        embedding: np.ndarray,
        primary_photo_url: str = None
    ) -> bool:
        """
        Store or update face embedding for a criminal.
        
        Args:
            criminal_id: Criminal ID
            embedding: Face embedding vector (512-dim)
            primary_photo_url: URL to primary photo
        
        Returns:
            True if successful
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Convert numpy array to bytes
                embedding_bytes = embedding.astype(np.float32).tobytes()
                
                query = """
                    UPDATE criminals
                    SET face_embedding = %s,
                        embedding_model = 'buffalo_sc',
                        embedding_dimension = %s,
                        primary_photo_url = COALESCE(%s, primary_photo_url),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE criminal_id = %s
                """
                
                cur.execute(query, (
                    embedding_bytes,
                    embedding.shape[0],
                    primary_photo_url,
                    criminal_id
                ))
                
                conn.commit()
                logger.info(f"Stored embedding for criminal ID: {criminal_id}")
                return True
    
    def get_all_embeddings(self) -> List[Dict]:
        """
        Retrieve all active criminal embeddings for comparison.
        
        Returns:
            List of dicts with criminal_id, name, embedding, and metadata
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        criminal_id,
                        name,
                        nic,
                        face_embedding,
                        primary_photo_url,
                        risk_level,
                        crime_history
                    FROM criminals
                    WHERE status = 'active'
                      AND face_embedding IS NOT NULL
                    ORDER BY criminal_id
                """
                
                cur.execute(query)
                results = cur.fetchall()
                
                # Convert embeddings from bytes to numpy arrays
                embeddings = []
                for row in results:
                    embedding_bytes = row['face_embedding']
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    
                    embeddings.append({
                        'criminal_id': row['criminal_id'],
                        'name': row['name'],
                        'nic': row['nic'],
                        'embedding': embedding,
                        'primary_photo_url': row['primary_photo_url'],
                        'risk_level': row['risk_level'],
                        'crime_history': row['crime_history']
                    })
                
                logger.info(f"Retrieved {len(embeddings)} criminal embeddings")
                return embeddings
    
    def get_criminal_details(self, criminal_id: int) -> Optional[Dict]:
        """
        Get full details for a specific criminal.
        
        Args:
            criminal_id: Criminal ID
        
        Returns:
            Dictionary with all criminal information
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        criminal_id, name, nic, alias, date_of_birth,
                        gender, address, nationality, crime_history,
                        primary_photo_url, status, risk_level,
                        created_at, updated_at, notes,
                        last_seen_location, last_seen_date
                    FROM criminals
                    WHERE criminal_id = %s
                """
                
                cur.execute(query, (criminal_id,))
                result = cur.fetchone()
                
                if result:
                    logger.info(f"Retrieved details for criminal ID: {criminal_id}")
                return result
    
    # ========================================================================
    # SUSPECT PHOTOS OPERATIONS
    # ========================================================================
    
    def store_suspect_photo(
        self,
        criminal_id: int,
        photo_url: str,
        photo_hash: str,
        embedding: np.ndarray,
        face_confidence: float,
        face_bbox: Dict,
        photo_quality: str,
        image_width: int,
        image_height: int,
        file_size_bytes: int,
        is_primary: bool = False,
        source: str = 'manual_upload',
        uploaded_by: int = None
    ) -> int:
        """
        Store a suspect photo with its embedding.
        
        Args:
            criminal_id: Criminal ID
            photo_url: Path to stored photo
            photo_hash: SHA-256 hash of photo
            embedding: Face embedding vector
            face_confidence: Detection confidence (0-1)
            face_bbox: Bounding box dict
            photo_quality: Quality assessment
            image_width: Image width in pixels
            image_height: Image height in pixels
            file_size_bytes: File size
            is_primary: Whether this is primary photo
            source: Source of photo
            uploaded_by: User ID
        
        Returns:
            photo_id: ID of stored photo
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Convert embedding to bytes
                embedding_bytes = embedding.astype(np.float32).tobytes()
                bbox_json = json.dumps(face_bbox)
                
                query = """
                    INSERT INTO suspect_photos (
                        criminal_id, photo_url, photo_hash, face_embedding,
                        face_confidence, face_bbox, is_primary, photo_quality,
                        image_width, image_height, file_size_bytes,
                        source, uploaded_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING photo_id
                """
                
                cur.execute(query, (
                    criminal_id, photo_url, photo_hash, embedding_bytes,
                    face_confidence, bbox_json, is_primary, photo_quality,
                    image_width, image_height, file_size_bytes,
                    source, uploaded_by
                ))
                
                result = cur.fetchone()
                conn.commit()
                
                photo_id = result['photo_id']
                logger.info(f"Stored photo: ID={photo_id}, Criminal={criminal_id}")
                return photo_id
    
    def get_criminal_photos(self, criminal_id: int) -> List[Dict]:
        """
        Get all photos for a criminal.
        
        Args:
            criminal_id: Criminal ID
        
        Returns:
            List of photo records
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        photo_id, photo_url, photo_quality,
                        is_primary, face_confidence, uploaded_at
                    FROM suspect_photos
                    WHERE criminal_id = %s
                    ORDER BY is_primary DESC, uploaded_at DESC
                """
                
                cur.execute(query, (criminal_id,))
                return cur.fetchall()
    
    # ========================================================================
    # FACIAL RECOGNITION LOGS
    # ========================================================================
    
    def log_recognition_request(
        self,
        uploaded_image_url: str,
        uploaded_image_hash: str,
        face_detected: bool,
        face_count: int,
        face_quality: str,
        matches_found: int,
        best_match_criminal_id: int,
        best_match_similarity: float,
        all_matches: List[Dict],
        processing_time_ms: int,
        requested_by: int = None,
        user_role: str = None,
        ip_address: str = None,
        case_id: str = None
    ) -> int:
        """
        Log a facial recognition request for audit trail.
        
        Args:
            uploaded_image_url: Path to uploaded image
            uploaded_image_hash: SHA-256 hash
            face_detected: Whether face was detected
            face_count: Number of faces
            face_quality: Quality assessment
            matches_found: Number of matches
            best_match_criminal_id: ID of best match
            best_match_similarity: Similarity score (0-100)
            all_matches: List of all matches
            processing_time_ms: Processing time
            requested_by: User ID
            user_role: User role
            ip_address: Request IP
            case_id: Investigation case ID
        
        Returns:
            log_id: ID of log entry
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    INSERT INTO facial_recognition_logs (
                        uploaded_image_url, uploaded_image_hash,
                        face_detected, face_count, face_quality,
                        matches_found, best_match_criminal_id,
                        best_match_similarity, all_matches,
                        processing_time_ms, requested_by, user_role,
                        ip_address, case_id, model_version
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'buffalo_sc_v1'
                    )
                    RETURNING log_id
                """
                
                all_matches_json = json.dumps(all_matches)
                
                cur.execute(query, (
                    uploaded_image_url, uploaded_image_hash,
                    face_detected, face_count, face_quality,
                    matches_found, best_match_criminal_id,
                    best_match_similarity, all_matches_json,
                    processing_time_ms, requested_by, user_role,
                    ip_address, case_id
                ))
                
                result = cur.fetchone()
                conn.commit()
                
                log_id = result['log_id']
                logger.info(f"Logged recognition request: ID={log_id}")
                return log_id
    
    def get_recognition_history(
        self,
        limit: int = 50,
        user_id: int = None
    ) -> List[Dict]:
        """
        Get recognition request history.
        
        Args:
            limit: Maximum number of records
            user_id: Filter by user ID (optional)
        
        Returns:
            List of log entries
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    query = """
                        SELECT * FROM facial_recognition_logs
                        WHERE requested_by = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cur.execute(query, (user_id, limit))
                else:
                    query = """
                        SELECT * FROM facial_recognition_logs
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cur.execute(query, (limit,))
                
                return cur.fetchall()
    
    def close(self):
        """Close the connection pool."""
        if self.pool:
            self.pool.close()
            logger.info("Database connection pool closed")


# Singleton instance
_db_instance = None

def get_database() -> FacialRecognitionDB:
    """
    Get singleton instance of database connection.
    
    Returns:
        FacialRecognitionDB instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = FacialRecognitionDB()
    return _db_instance
