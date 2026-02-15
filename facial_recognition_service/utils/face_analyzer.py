"""
Face Analyzer Module
====================
Wrapper for InsightFace model to extract and compare face embeddings.

This module provides industry-standard facial recognition capabilities:
- Face detection and alignment
- Embedding extraction using buffalo_sc model
- Similarity calculation (cosine distance)
- Multi-face handling with quality scoring
- Supabase integration for cloud image processing
"""

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from typing import List, Dict, Optional, Union
import os
import logging
from pathlib import Path
import tempfile
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceAnalyzer:
    """
    High-performance face analysis using InsightFace buffalo_sc model.
    
    Features:
    - 512-dimensional face embeddings
    - Multi-face detection
    - Quality assessment
    - Normalized embeddings for accurate comparison
    - Cloud image support (download from URL)
    """
    
    def __init__(self, model_name: str = 'buffalo_sc', model_root: str = 'model'):
        """
        Initialize InsightFace model.
        
        Args:
            model_name: InsightFace model name (default: buffalo_sc)
            model_root: Path to model directory
        """
        self.model_name = model_name
        self.model_root = model_root
        self.embedding_dim = 512
        
        # Get absolute path for model root
        base_dir = Path(__file__).parent.parent
        self.model_root = str(base_dir / model_root)
        
        # Ensure model directory exists
        os.makedirs(self.model_root, exist_ok=True)
        
        # Initialize InsightFace application
        logger.info(f"Loading InsightFace model: {model_name} from {self.model_root}")
        try:
            self.app = FaceAnalysis(
                name=model_name,
                root=self.model_root,
                providers=['CPUExecutionProvider']  # Use CPU for compatibility
            )
            self.app.prepare(ctx_id=-1, det_size=(640, 640))  # Higher resolution for better accuracy
            logger.info("✓ Face analysis model loaded successfully")
        except Exception as e:
            logger.error(f"✗ Failed to load model: {str(e)}")
            raise
    
    def download_image_from_url(self, url: str) -> Optional[np.ndarray]:
        """
        Download image from URL and return as numpy array.
        
        Args:
            url: Image URL (Supabase Storage or any public URL)
        
        Returns:
            Image as numpy array (BGR format), or None if failed
        """
        try:
            logger.info(f"Downloading image from URL: {url[:80]}...")
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                
            # Convert to numpy array
            nparr = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logger.error(f"Failed to decode image from URL")
                return None
            
            logger.info(f"✓ Downloaded image: {img.shape[1]}x{img.shape[0]}")
            return img
            
        except Exception as e:
            logger.error(f"Failed to download image: {str(e)}")
            return None
    
    def extract_embedding(
        self, 
        image_path: str = None, 
        image_bytes: bytes = None,
        image_array: np.ndarray = None,
        image_url: str = None
    ) -> Optional[Dict]:
        """
        Extract face embedding from an image.
        
        Args:
            image_path: Path to image file
            image_bytes: Image as bytes
            image_array: Image as numpy array (BGR format)
            image_url: URL to download image from (Supabase Storage)
        
        Returns:
            Dictionary with:
            - embedding: 512-dim normalized vector (np.ndarray)
            - confidence: Detection confidence (0-1)
            - bbox: Bounding box [x1, y1, x2, y2]
            - quality: Quality score ('low', 'medium', 'high', 'excellent')
            - face_count: Number of faces detected
            
            Returns None if no face detected
        """
        # Load image from various sources
        img = None
        
        if image_array is not None:
            img = image_array
        elif image_url is not None:
            img = self.download_image_from_url(image_url)
        elif image_path is not None:
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image: {image_path}")
        elif image_bytes is not None:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.error("Failed to decode image bytes")
        
        if img is None:
            logger.error("No valid image source provided or image loading failed")
            return None
        
        # Detect faces
        try:
            faces = self.app.get(img)
        except Exception as e:
            logger.error(f"Face detection failed: {str(e)}")
            return None
        
        if not faces:
            logger.warning("No faces detected in image")
            return {
                'embedding': None,
                'confidence': 0.0,
                'bbox': None,
                'quality': 'none',
                'face_count': 0
            }
        
        # Use the largest/most confident face if multiple detected
        if len(faces) > 1:
            logger.info(f"Multiple faces detected ({len(faces)}), using most confident")
            faces = sorted(faces, key=lambda x: x.det_score, reverse=True)
        
        face = faces[0]
        
        # Extract and normalize embedding
        embedding = face.embedding
        norm = np.linalg.norm(embedding)
        normalized_embedding = embedding / norm if norm > 0 else embedding
        
        # Calculate quality score based on detection confidence and face size
        bbox = face.bbox.astype(int)
        face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        image_area = img.shape[0] * img.shape[1]
        face_ratio = face_area / image_area if image_area > 0 else 0
        
        # Quality assessment
        confidence = float(face.det_score)
        if confidence > 0.95 and face_ratio > 0.1:
            quality = 'excellent'
        elif confidence > 0.85 and face_ratio > 0.05:
            quality = 'high'
        elif confidence > 0.75:
            quality = 'medium'
        else:
            quality = 'low'
        
        return {
            'embedding': normalized_embedding,
            'confidence': confidence,
            'bbox': bbox.tolist(),
            'quality': quality,
            'face_count': len(faces),
            'face_area_ratio': float(face_ratio),
            'image_dimensions': {'width': img.shape[1], 'height': img.shape[0]}
        }
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two face embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        
        Returns:
            Similarity score (0-1, where 1 is identical)
        """
        # Ensure embeddings are normalized
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        emb1_normalized = embedding1 / norm1
        emb2_normalized = embedding2 / norm2
        
        # Cosine similarity using dot product
        similarity = np.dot(emb1_normalized, emb2_normalized)
        
        # Ensure result is in [0, 1] range
        similarity = float(np.clip(similarity, 0.0, 1.0))
        
        return similarity
    
    def calculate_average_embedding(self, embeddings: List[np.ndarray]) -> Optional[np.ndarray]:
        """
        Calculate average embedding from multiple face photos.
        
        This improves accuracy by combining multiple samples of the same person.
        
        Args:
            embeddings: List of embedding vectors
        
        Returns:
            Average normalized embedding
        """
        if not embeddings:
            return None
        
        if len(embeddings) == 1:
            return embeddings[0]
        
        # Stack and average
        stacked = np.stack(embeddings)
        avg_embedding = np.mean(stacked, axis=0)
        
        # Normalize the average
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm
        
        logger.info(f"Averaged {len(embeddings)} embeddings")
        return avg_embedding
    
    def find_best_match(
        self,
        suspect_embedding: np.ndarray,
        criminal_embeddings: List[Dict],
        threshold: float = 0.45
    ) -> List[Dict]:
        """
        Find matching criminals from database embeddings.
        
        Args:
            suspect_embedding: Embedding of suspect to match
            criminal_embeddings: List of dicts with 'criminal_id', 'name', 'embedding'
            threshold: Minimum similarity threshold (0-1, default 0.45 = 45%)
        
        Returns:
            List of matches sorted by similarity (descending), each containing:
            - criminal_id
            - name
            - similarity (0-1)
            - similarity_percentage (0-100)
            - confidence_level ('high', 'medium', 'low')
        """
        matches = []
        
        for criminal in criminal_embeddings:
            if criminal.get('embedding') is None:
                continue
                
            similarity = self.calculate_similarity(
                suspect_embedding,
                criminal['embedding']
            )
            
            if similarity >= threshold:
                # Determine confidence level (adjusted for realistic face matching)
                if similarity >= 0.65:
                    confidence = 'high'
                elif similarity >= 0.50:
                    confidence = 'medium'
                else:
                    confidence = 'low'
                
                matches.append({
                    'criminal_id': criminal['criminal_id'],
                    'name': criminal.get('name', 'Unknown'),
                    'nic': criminal.get('nic', ''),
                    'similarity': float(similarity),
                    'similarity_percentage': float(similarity * 100),
                    'confidence_level': confidence,
                    'photo_url': criminal.get('photo_url'),
                    'risk_level': criminal.get('risk_level'),
                    'crime_history': criminal.get('crime_history'),
                })
        
        # Sort by similarity (descending)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Found {len(matches)} matches above threshold {threshold}")
        return matches
    
    def embedding_to_list(self, embedding: np.ndarray) -> List[float]:
        """
        Convert embedding numpy array to list for JSON/database storage.
        
        Args:
            embedding: Numpy array (float32)
        
        Returns:
            List of floats
        """
        return embedding.astype(np.float32).tolist()
    
    def list_to_embedding(self, embedding_list: List[float]) -> np.ndarray:
        """
        Convert list from database back to numpy array.
        
        Args:
            embedding_list: List of floats from database
        
        Returns:
            Numpy array (float32)
        """
        return np.array(embedding_list, dtype=np.float32)
    
    def validate_embedding(self, embedding: Union[np.ndarray, List[float]]) -> bool:
        """
        Validate that embedding is correct format.
        
        Args:
            embedding: Numpy array or list to validate
        
        Returns:
            True if valid, False otherwise
        """
        if embedding is None:
            return False
        
        # Convert list to array if needed
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        
        if not isinstance(embedding, np.ndarray):
            return False
        
        if embedding.shape != (self.embedding_dim,):
            logger.warning(f"Invalid embedding shape: {embedding.shape}, expected ({self.embedding_dim},)")
            return False
        
        if not np.isfinite(embedding).all():
            logger.warning("Embedding contains non-finite values")
            return False
        
        return True


# Singleton instance for reuse across requests
_face_analyzer_instance = None

def get_face_analyzer() -> FaceAnalyzer:
    """
    Get singleton instance of FaceAnalyzer.
    
    This ensures the model is loaded only once for performance.
    """
    global _face_analyzer_instance
    if _face_analyzer_instance is None:
        _face_analyzer_instance = FaceAnalyzer()
    return _face_analyzer_instance
