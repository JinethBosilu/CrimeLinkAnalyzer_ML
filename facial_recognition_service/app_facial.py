"""
Facial Recognition Service
===========================
FastAPI microservice for criminal facial recognition using InsightFace.

Features:
- Suspect image upload and analysis
- Criminal registration with multiple photos
- Match history retrieval
- Audit logging
- JWT authentication support

Endpoints:
- POST /analyze: Analyze suspect image
- POST /register-criminal: Register new criminal
- GET /matches/{analysis_id}: Get match details
- GET /health: Health check
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging
import os
from pathlib import Path
import json

from utils.face_analyzer import get_face_analyzer
from utils.database import get_database
from utils.image_storage import get_image_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Facial Recognition Service",
    description="Criminal facial recognition using InsightFace",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],  # Frontend and backend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
face_analyzer = None
database = None
storage = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global face_analyzer, database, storage
    
    try:
        logger.info("Initializing Facial Recognition Service...")
        
        # Initialize face analyzer
        face_analyzer = get_face_analyzer()
        logger.info("✓ Face analyzer initialized")
        
        # Initialize database
        database = get_database()
        logger.info("✓ Database connection established")
        
        # Initialize storage
        storage = get_image_storage()
        logger.info("✓ Image storage initialized")
        
        logger.info("Facial Recognition Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize service: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Facial Recognition Service...")


# ============================================================================
# Pydantic Models
# ============================================================================

class MatchResult(BaseModel):
    """Match result model."""
    criminal_id: int
    name: str
    nic: str
    similarity: float = Field(..., description="Similarity percentage (0-100)")
    confidence_level: str = Field(..., description="high, medium, or low")
    crime_history: Optional[dict] = None
    risk_level: Optional[str] = None
    last_seen: Optional[str] = None
    photo_url: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Analysis response model."""
    analysis_id: int
    found_matches: bool
    match_count: int
    matches: List[MatchResult]
    processing_time_ms: float
    timestamp: str


class CriminalRegistration(BaseModel):
    """Criminal registration model."""
    criminal_id: int
    name: str
    nic: str
    photos_stored: int
    embedding_quality: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    services: dict


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and component health.
    """
    try:
        # Check database connection
        db_healthy = database is not None
        
        # Check face analyzer
        analyzer_healthy = face_analyzer is not None
        
        # Check storage
        storage_healthy = storage is not None and storage.base_dir.exists()
        
        return {
            "status": "healthy" if all([db_healthy, analyzer_healthy, storage_healthy]) else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "ok" if db_healthy else "error",
                "face_analyzer": "ok" if analyzer_healthy else "error",
                "storage": "ok" if storage_healthy else "error"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_suspect(
    image: UploadFile = File(..., description="Suspect image (JPG/PNG, max 5MB)"),
    threshold: float = 45.0,  # Lowered from 75% to 45% for realistic matching
    user_id: Optional[str] = Form(None)
):
    """
    Analyze suspect image and find matches.
    
    Args:
        image: Suspect photo
        threshold: Minimum similarity threshold (0-100)
        user_id: Optional user ID for audit logging
    
    Returns:
        Analysis results with matches above threshold
    """
    start_time = datetime.now()
    temp_file_path = None
    
    try:
        # Validate file type
        if not image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read file bytes
        file_bytes = await image.read()
        
        # Store temporarily
        temp_file_path, file_hash, file_size = storage.store_uploaded_file(
            file_bytes=file_bytes,
            filename=image.filename,
            criminal_id=None  # Temporary storage
        )
        
        logger.info(f"Processing suspect image: {image.filename} ({file_size} bytes)")
        
        # Extract embedding from suspect image
        result = face_analyzer.extract_embedding(temp_file_path)
        
        if result is None or result['embedding'] is None:
            raise HTTPException(
                status_code=400,
                detail="No face detected in image. Please upload a clear photo with visible face."
            )
        
        suspect_embedding = result['embedding']
        quality = result['quality']
        
        logger.info(f"Extracted embedding with quality: {quality}")
        
        # Get all criminal embeddings from database
        criminals = database.get_all_embeddings()
        
        if not criminals:
            # No criminals in database
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Convert user_id to int or None
            user_id_int = int(user_id) if user_id and user_id.isdigit() else None
            
            # Log request
            database.log_recognition_request(
                uploaded_image_url=str(temp_file_path),
                uploaded_image_hash=file_hash,
                face_detected=True,
                face_count=1,
                face_quality=quality,
                matches_found=0,
                best_match_criminal_id=None,
                best_match_similarity=0.0,
                all_matches=[],
                processing_time_ms=int(processing_time),
                requested_by=user_id_int
            )
            
            return {
                "analysis_id": 0,
                "found_matches": False,
                "match_count": 0,
                "matches": [],
                "processing_time_ms": processing_time,
                "timestamp": datetime.now().isoformat()
            }
        
        # Find best matches
        matches = face_analyzer.find_best_match(
            suspect_embedding=suspect_embedding,
            criminal_embeddings=criminals,
            threshold=threshold / 100.0  # Convert percentage to 0-1
        )
        
        # Format matches
        match_results = []
        for match in matches:
            # Get full criminal details
            criminal_details = database.get_criminal_details(match['criminal_id'])
            
            match_results.append({
                "criminal_id": match['criminal_id'],
                "name": criminal_details['name'],
                "nic": criminal_details['nic'],
                "similarity": match['similarity'] * 100,  # Convert to percentage
                "confidence_level": match['confidence_level'],
                "crime_history": criminal_details.get('crime_history'),
                "risk_level": criminal_details.get('risk_level'),
                "last_seen": criminal_details.get('last_seen'),
                "photo_url": None  # TODO: Implement photo retrieval
            })
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Convert user_id to int or None
        user_id_int = int(user_id) if user_id and user_id.isdigit() else None
        
        # Log request to database
        analysis_id = database.log_recognition_request(
            uploaded_image_url=str(temp_file_path),
            uploaded_image_hash=file_hash,
            face_detected=True,
            face_count=1,
            face_quality=quality,
            matches_found=len(match_results),
            best_match_criminal_id=match_results[0]['criminal_id'] if match_results else None,
            best_match_similarity=match_results[0]['similarity'] if match_results else 0.0,
            all_matches=match_results,
            processing_time_ms=int(processing_time),
            requested_by=user_id_int
        )
        
        logger.info(f"Analysis complete: {len(match_results)} matches found (threshold: {threshold}%)")
        
        return {
            "analysis_id": analysis_id,
            "found_matches": len(match_results) > 0,
            "match_count": len(match_results),
            "matches": match_results,
            "processing_time_ms": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {str(e)}")


@app.post("/register-criminal", response_model=CriminalRegistration)
async def register_criminal(
    name: str = Form(..., description="Criminal name"),
    nic: str = Form(..., description="National Identity Card number"),
    crime_history: Optional[str] = Form(None, description="JSON string of crime history"),
    risk_level: str = Form("medium", description="low, medium, high, or critical"),
    photos: List[UploadFile] = File(..., description="Criminal photos (1-5 images)"),
    user_id: Optional[str] = Form(None)
):
    """
    Register new criminal with photos.
    
    Args:
        name: Criminal name
        nic: NIC number
        crime_history: JSON string of crime records
        risk_level: Risk level
        photos: List of photos (1-5)
        user_id: Optional user ID
    
    Returns:
        Registration confirmation
    """
    try:
        # Validate photos count
        if not photos or len(photos) == 0:
            raise HTTPException(status_code=400, detail="At least one photo required")
        
        if len(photos) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 photos allowed")
        
        # Parse crime history
        crime_history_json = None
        if crime_history:
            try:
                crime_history_json = json.loads(crime_history)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid crime_history JSON")
        
        logger.info(f"Registering criminal: {name} (NIC: {nic}) with {len(photos)} photos")
        
        # Create criminal record
        criminal_id = database.create_criminal(
            name=name,
            nic=nic,
            crime_history=crime_history_json,
            risk_level=risk_level
        )
        
        # Process each photo
        embeddings = []
        stored_photos = 0
        
        for idx, photo in enumerate(photos):
            try:
                # Validate file type
                if not photo.content_type.startswith('image/'):
                    logger.warning(f"Skipping non-image file: {photo.filename}")
                    continue
                
                # Read file bytes
                file_bytes = await photo.read()
                
                # Store image
                image_path, file_hash, file_size = storage.store_uploaded_file(
                    file_bytes=file_bytes,
                    filename=photo.filename,
                    criminal_id=criminal_id
                )
                
                # Extract embedding
                result = face_analyzer.extract_embedding(image_path)
                
                if result is not None and result['embedding'] is not None:
                    embedding = result['embedding']
                    quality = result['quality']
                    embeddings.append(embedding)
                    
                    # Store photo metadata in database
                    database.store_suspect_photo(
                        criminal_id=criminal_id,
                        image_path=image_path,
                        file_hash=file_hash,
                        embedding=embedding,
                        quality=quality,
                        is_primary=(idx == 0)
                    )
                    
                    stored_photos += 1
                    logger.info(f"Stored photo {idx + 1}/{len(photos)}: quality={quality}")
                else:
                    logger.warning(f"No face detected in photo {idx + 1}")
                    
            except Exception as e:
                logger.error(f"Failed to process photo {idx + 1}: {str(e)}")
                continue
        
        if stored_photos == 0:
            raise HTTPException(
                status_code=400,
                detail="No valid faces detected in any photos"
            )
        
        # Calculate average embedding
        avg_embedding = face_analyzer.calculate_average_embedding(embeddings)
        
        # Determine quality from stored photos
        qualities = ["excellent", "high", "medium", "low"]
        overall_quality = qualities[min(len(embeddings) - 1, 2)]  # More photos = better quality
        
        # Store average embedding
        database.store_criminal_embedding(
            criminal_id=criminal_id,
            embedding=avg_embedding,
            photo_count=stored_photos,
            embedding_quality=overall_quality
        )
        
        logger.info(f"Criminal registered successfully: ID={criminal_id}, photos={stored_photos}")
        
        return {
            "criminal_id": criminal_id,
            "name": name,
            "nic": nic,
            "photos_stored": stored_photos,
            "embedding_quality": overall_quality,
            "message": f"Successfully registered with {stored_photos} photo(s)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.get("/matches/{analysis_id}")
async def get_match_details(analysis_id: int):
    """
    Get detailed match information for an analysis.
    
    Args:
        analysis_id: Analysis ID from previous analysis
    
    Returns:
        Match details from database
    """
    try:
        # Get recognition history for this analysis
        history = database.get_recognition_history(limit=100)
        
        # Find matching record
        match_record = None
        for record in history:
            if record.get('id') == analysis_id:
                match_record = record
                break
        
        if not match_record:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return {
            "analysis_id": analysis_id,
            "timestamp": match_record.get('created_at'),
            "matches_found": match_record.get('matches_found', 0),
            "top_match_id": match_record.get('top_match_id'),
            "similarity": match_record.get('similarity_score'),
            "processing_time_ms": match_record.get('processing_time_ms'),
            "user_id": match_record.get('user_id'),
            "match_details": match_record.get('match_details')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get match details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_analysis_history(
    user_id: Optional[str] = None,
    limit: int = 50
):
    """
    Get recognition history.
    
    Args:
        user_id: Filter by user ID
        limit: Maximum records to return
    
    Returns:
        List of recognition history records
    """
    try:
        history = database.get_recognition_history(user_id=user_id, limit=limit)
        return {
            "count": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(f"Failed to get history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "5002"))
    
    uvicorn.run(
        "app_facial:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
