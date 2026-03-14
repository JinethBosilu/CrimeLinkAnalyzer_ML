"""
Facial Recognition Service
===========================
FastAPI microservice for criminal facial recognition using InsightFace.
Integrates with Supabase Storage for cloud image management.

Features:
- Suspect image upload and analysis
- Criminal registration with multiple photos (stored in Supabase)
- Match history retrieval
- Audit logging
- Real-time face matching against criminal database

Endpoints:
- POST /analyze: Analyze suspect image and find matches
- POST /register: Register new criminal with photos
- GET /criminals: List all registered criminals
- GET /criminals/{id}: Get criminal details
- GET /history: Get recognition history
- GET /health: Health check
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
import hashlib
import tempfile

from utils.face_analyzer import get_face_analyzer
from utils.database import get_database
from utils.supabase_storage import get_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Facial Recognition Service",
    description="Criminal facial recognition using InsightFace + Supabase Storage",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration - read from environment variable
cors_origins_str = os.environ.get("CORS_ORIGINS", "*")
if cors_origins_str == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
face_analyzer = None
database = None
storage = None


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global face_analyzer, database, storage
    
    try:
        logger.info("=" * 60)
        logger.info("Initializing Facial Recognition Service...")
        logger.info("=" * 60)
        
        # Initialize face analyzer (loads InsightFace model)
        face_analyzer = get_face_analyzer()
        logger.info("✓ Face analyzer initialized (buffalo_sc model)")
        
        # Initialize database
        database = get_database()
        database.ensure_audit_table_exists()
        logger.info("✓ Database connection established (Supabase PostgreSQL)")
        
        # Initialize storage
        storage = get_storage()
        logger.info("✓ Supabase Storage initialized")
        
        logger.info("=" * 60)
        logger.info("Facial Recognition Service started successfully!")
        logger.info(f"Docs: http://0.0.0.0:{os.environ.get('PORT', '5002')}/docs")
        logger.info("=" * 60)
        
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

class CrimeRecord(BaseModel):
    """Single crime record."""
    type: str
    date: str
    location: str
    description: Optional[str] = None


class CrimeHistory(BaseModel):
    """Crime history information."""
    total_crimes: int
    last_crime_date: Optional[str] = None
    crime_types: List[str] = []
    records: List[CrimeRecord] = []


class MatchResult(BaseModel):
    """Single match result."""
    criminal_id: str
    name: str
    nic: str
    similarity: float = Field(..., description="Similarity percentage (0-100)")
    confidence_level: str = Field(..., description="high, medium, or low")
    risk_level: Optional[str] = None
    photo_url: Optional[str] = None
    crime_history: Optional[CrimeHistory] = None


class AnalysisResponse(BaseModel):
    """Analysis response model."""
    analysis_id: int
    found_matches: bool
    match_count: int
    matches: List[MatchResult]
    face_detected: bool
    face_quality: str
    processing_time_ms: float
    timestamp: str


class CriminalRegistration(BaseModel):
    """Criminal registration response."""
    criminal_id: str
    name: str
    nic: str
    photos_stored: int
    embedding_quality: str
    message: str


class CriminalInfo(BaseModel):
    """Criminal information."""
    id: str
    name: str
    nic: str
    risk_level: Optional[str] = None
    primary_photo_url: Optional[str] = None
    status: Optional[str] = None
    has_embedding: bool = False


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - service info."""
    return {
        "service": "Facial Recognition Service",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and component health.
    """
    try:
        # Check database connection
        db_healthy = database is not None
        if db_healthy:
            try:
                criminals = database.get_all_criminals()
                db_healthy = True
            except:
                db_healthy = False
        
        # Check face analyzer
        analyzer_healthy = face_analyzer is not None
        
        # Check storage
        storage_healthy = storage is not None
        
        all_healthy = all([db_healthy, analyzer_healthy, storage_healthy])
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
            "services": {
                "database": "ok" if db_healthy else "error",
                "face_analyzer": "ok" if analyzer_healthy else "error",
                "storage": "ok" if storage_healthy else "error",
                "model": "buffalo_sc"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
            "services": {"error": str(e)}
        }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_suspect(
    request: Request,
    image: UploadFile = File(..., description="Suspect image (JPG/PNG)"),
    threshold: float = Query(45.0, description="Minimum similarity threshold (0-100)"),
    user_id: Optional[str] = Form(None),
    case_id: Optional[str] = Form(None)
):
    """
    Analyze suspect image and find matches in criminal database.
    
    Args:
        image: Suspect photo to analyze
        threshold: Minimum similarity percentage (0-100, default: 45)
        user_id: Optional user ID for audit logging
        case_id: Optional case ID for audit logging
    
    Returns:
        Analysis results with matches above threshold
    """
    start_time = datetime.now()
    temp_file_path = None
    
    try:
        # Validate file type
        if not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image (JPG/PNG)")
        
        # Read file bytes
        file_bytes = await image.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        logger.info(f"Processing suspect image: {image.filename} ({len(file_bytes)} bytes)")
        
        # Save to temp file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(file_bytes)
            temp_file_path = tmp.name
        
        # Extract embedding from suspect image
        result = face_analyzer.extract_embedding(image_path=temp_file_path)
        
        if result is None or result.get('embedding') is None:
            # No face detected
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log request
            analysis_id = database.log_recognition_request(
                uploaded_image_url="temp_upload",
                uploaded_image_hash=file_hash,
                face_detected=False,
                face_count=0,
                face_quality='none',
                matches_found=0,
                best_match_criminal_id=None,
                best_match_similarity=0.0,
                all_matches=[],
                processing_time_ms=int(processing_time),
                requested_by=user_id,
                case_id=case_id
            )
            
            return {
                "analysis_id": analysis_id,
                "found_matches": False,
                "match_count": 0,
                "matches": [],
                "face_detected": False,
                "face_quality": "none",
                "processing_time_ms": processing_time,
                "timestamp": datetime.now().isoformat()
            }
        
        suspect_embedding = result['embedding']
        quality = result['quality']
        face_count = result.get('face_count', 1)
        
        logger.info(f"Extracted embedding with quality: {quality}, faces detected: {face_count}")
        
        # Get all criminal embeddings from database
        criminals = database.get_all_embeddings()
        
        if not criminals:
            # No criminals with embeddings in database
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            analysis_id = database.log_recognition_request(
                uploaded_image_url="temp_upload",
                uploaded_image_hash=file_hash,
                face_detected=True,
                face_count=face_count,
                face_quality=quality,
                matches_found=0,
                best_match_criminal_id=None,
                best_match_similarity=0.0,
                all_matches=[],
                processing_time_ms=int(processing_time),
                requested_by=user_id,
                case_id=case_id
            )
            
            return {
                "analysis_id": analysis_id,
                "found_matches": False,
                "match_count": 0,
                "matches": [],
                "face_detected": True,
                "face_quality": quality,
                "processing_time_ms": processing_time,
                "timestamp": datetime.now().isoformat()
            }
        
        # Find best matches
        matches = face_analyzer.find_best_match(
            suspect_embedding=suspect_embedding,
            criminal_embeddings=criminals,
            threshold=threshold / 100.0  # Convert percentage to 0-1
        )
        
        # Format matches for response
        match_results = []
        for match in matches:
            # Parse crime_history — handle string (TEXT column), dict (JSONB), or list
            crime_history = match.get('crime_history')
            formatted_crime_history = None

            # Step 1: If it's a JSON string, parse it into a dict/list first
            if crime_history and isinstance(crime_history, str):
                try:
                    crime_history = json.loads(crime_history)
                except (json.JSONDecodeError, TypeError):
                    # Plain text — wrap as a single record
                    crime_history = {
                        "records": [{"type": "Unknown", "date": "", "location": "", "description": crime_history}],
                        "total_crimes": 1,
                        "crime_types": ["Unknown"],
                        "last_crime_date": ""
                    }

            # Step 2: Normalize into dict with records/total_crimes/crime_types/last_crime_date
            if crime_history and isinstance(crime_history, list):
                # Bare array of record objects
                records = crime_history
                crime_types = list(set(r.get('type', '') for r in records if r.get('type')))
                dates = sorted([r.get('date', '') for r in records if r.get('date')], reverse=True)
                crime_history = {
                    "records": records,
                    "total_crimes": len(records),
                    "crime_types": crime_types,
                    "last_crime_date": dates[0] if dates else ""
                }

            if crime_history and isinstance(crime_history, dict):
                records = crime_history.get('records', [])
                if not isinstance(records, list):
                    records = []
                crime_types = crime_history.get('crime_types', [])
                if not crime_types:
                    crime_types = list(set(r.get('type', '') for r in records if r.get('type')))
                last_crime_date = crime_history.get('last_crime_date', '')
                if not last_crime_date and records:
                    dates = sorted([r.get('date', '') for r in records if r.get('date')], reverse=True)
                    last_crime_date = dates[0] if dates else ''
                total_crimes = crime_history.get('total_crimes', len(records))

                if records or total_crimes > 0:
                    formatted_crime_history = {
                        "total_crimes": total_crimes,
                        "last_crime_date": last_crime_date,
                        "crime_types": crime_types,
                        "records": records[:5]  # Limit to 5 most recent
                    }
            
            match_results.append({
                "criminal_id": str(match['criminal_id']),
                "name": match['name'],
                "nic": match.get('nic', ''),
                "similarity": match['similarity_percentage'],
                "confidence_level": match['confidence_level'],
                "risk_level": match.get('risk_level'),
                "photo_url": match.get('photo_url'),
                "crime_history": formatted_crime_history
            })
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Log request to database (non-fatal — FK schema may differ)
        analysis_id = 0
        try:
            analysis_id = database.log_recognition_request(
                uploaded_image_url="temp_upload",
                uploaded_image_hash=file_hash,
                face_detected=True,
                face_count=face_count,
                face_quality=quality,
                matches_found=len(match_results),
                best_match_criminal_id=match_results[0]['criminal_id'] if match_results else None,
                best_match_similarity=match_results[0]['similarity'] if match_results else 0.0,
                all_matches=match_results,
                processing_time_ms=int(processing_time),
                requested_by=user_id,
                case_id=case_id
            )
        except Exception as log_err:
            logger.warning(f"Could not log recognition request (non-fatal): {log_err}")
        
        logger.info(f"Analysis complete: {len(match_results)} matches found (threshold: {threshold}%)")
        
        # Debug: Log match_results with crime_history
        for m in match_results:
            logger.info(f"Match: {m.get('name')} - crime_history: {m.get('crime_history')}")
        
        return {
            "analysis_id": analysis_id,
            "found_matches": len(match_results) > 0,
            "match_count": len(match_results),
            "matches": match_results,
            "face_detected": True,
            "face_quality": quality,
            "processing_time_ms": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {str(e)}")


@app.post("/register", response_model=CriminalRegistration)
async def register_criminal(
    name: str = Form(..., description="Criminal name"),
    nic: str = Form(..., description="National Identity Card number"),
    risk_level: str = Form("medium", description="low, medium, high, or critical"),
    crime_history: Optional[str] = Form(None, description="Crime history text"),
    address: Optional[str] = Form(None, description="Criminal address"),
    contact_number: Optional[str] = Form(None, description="Contact phone number"),
    secondary_contact: Optional[str] = Form(None, description="Secondary contact number"),
    date_of_birth: Optional[str] = Form(None, description="Date of birth (YYYY-MM-DD)"),
    gender: Optional[str] = Form(None, description="Gender (Male/Female/Other)"),
    alias: Optional[str] = Form(None, description="Known alias"),
    status: Optional[str] = Form("active", description="Status (active/inactive/archived)"),
    photos: List[UploadFile] = File(..., description="Criminal photos (1-5 images)")
):
    """
    Register new criminal with photos.
    
    Photos are uploaded to Supabase Storage and embeddings are extracted
    for face matching.
    
    Args:
        name: Criminal name
        nic: NIC number
        risk_level: Risk level (low/medium/high/critical)
        crime_history: Optional crime history
        address: Optional address
        contact_number: Optional phone number
        secondary_contact: Optional secondary phone
        date_of_birth: Optional date of birth
        gender: Optional gender
        alias: Optional alias
        status: Status (default: active)
        photos: List of photos (1-5)
    
    Returns:
        Registration confirmation with criminal ID
    """
    try:
        # Validate photos count
        if not photos or len(photos) == 0:
            raise HTTPException(status_code=400, detail="At least one photo required")
        
        if len(photos) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 photos allowed")
        
        logger.info(f"Registering criminal: {name} (NIC: {nic}) with {len(photos)} photos")
        
        # Create criminal record
        criminal_id = database.create_criminal(
            name=name,
            nic=nic,
            crime_history=crime_history,
            risk_level=risk_level,
            address=address,
            contact_number=contact_number,
            secondary_contact=secondary_contact,
            date_of_birth=date_of_birth,
            gender=gender,
            alias=alias,
            status=status or 'active'
        )
        
        logger.info(f"Created criminal record: {criminal_id}")
        
        # Process each photo
        embeddings = []
        stored_photos = 0
        primary_photo_url = None
        
        for idx, photo in enumerate(photos):
            try:
                # Validate file type
                if not photo.content_type or not photo.content_type.startswith('image/'):
                    logger.warning(f"Skipping non-image file: {photo.filename}")
                    continue
                
                # Read file bytes
                file_bytes = await photo.read()
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                
                # Save to temp file for processing
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    tmp.write(file_bytes)
                    temp_path = tmp.name
                
                try:
                    # Extract embedding
                    result = face_analyzer.extract_embedding(image_path=temp_path)
                    
                    if result is not None and result.get('embedding') is not None:
                        embedding = result['embedding']
                        quality = result['quality']
                        confidence = result['confidence']
                        
                        # Upload to Supabase Storage
                        storage_result = storage.upload_image(
                            file_path=temp_path,
                            criminal_id=criminal_id,
                            filename=f"{idx}_{photo.filename}"
                        )
                        
                        if storage_result:
                            photo_url = storage_result['url']
                            
                            if idx == 0:
                                primary_photo_url = photo_url
                            
                            embeddings.append(embedding)
                            
                            # Store photo metadata in database
                            database.store_suspect_photo(
                                criminal_id=criminal_id,
                                photo_url=photo_url,
                                photo_hash=file_hash,
                                embedding=face_analyzer.embedding_to_list(embedding),
                                face_confidence=confidence,
                                face_bbox=result.get('bbox'),
                                photo_quality=0.0,
                                image_width=result.get('image_dimensions', {}).get('width', 0),
                                image_height=result.get('image_dimensions', {}).get('height', 0),
                                file_size_bytes=len(file_bytes),
                                is_primary=(idx == 0)
                            )
                            
                            stored_photos += 1
                            logger.info(f"Stored photo {idx + 1}/{len(photos)}: quality={quality}")
                        else:
                            logger.warning(f"Failed to upload photo {idx + 1} to storage")
                    else:
                        logger.warning(f"No face detected in photo {idx + 1}")
                        
                finally:
                    # Cleanup temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        
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
        overall_quality = qualities[min(stored_photos - 1, 2)]
        
        # Store average embedding
        database.update_criminal_embedding(
            criminal_id=criminal_id,
            embedding=face_analyzer.embedding_to_list(avg_embedding),
            primary_photo_url=primary_photo_url
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


class EmbeddingResponse(BaseModel):
    """Response for embedding generation."""
    criminal_id: str
    has_embedding: bool
    photos_processed: int
    message: str


@app.post("/generate-embedding", response_model=EmbeddingResponse)
async def generate_embedding(
    criminal_id: str = Form(..., description="Existing criminal ID"),
    photo: UploadFile = File(..., description="Photo to generate embedding from")
):
    """
    Generate a face embedding for an existing criminal record.
    
    This endpoint is called by Spring Boot after creating/updating a criminal
    record. It extracts the face embedding from the provided photo and stores
    it in the database. It does NOT create a new criminal record.
    
    Args:
        criminal_id: The existing criminal's ID
        photo: Photo file to extract embedding from
    
    Returns:
        Confirmation with embedding status
    """
    temp_path = None
    try:
        # Validate photo
        if not photo.content_type or not photo.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        logger.info(f"Generating embedding for criminal: {criminal_id}")
        
        # Read file bytes
        file_bytes = await photo.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        # Save to temp file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(file_bytes)
            temp_path = tmp.name
        
        # Extract embedding using InsightFace
        result = face_analyzer.extract_embedding(image_path=temp_path)
        
        if result is None or result.get('embedding') is None:
            logger.warning(f"No face detected in photo for criminal {criminal_id}")
            return {
                "criminal_id": criminal_id,
                "has_embedding": False,
                "photos_processed": 0,
                "message": "No face detected in the provided photo"
            }
        
        embedding = result['embedding']
        confidence = result['confidence']
        
        # Upload to Supabase Storage (will overwrite if exists thanks to upsert)
        storage_result = storage.upload_image(
            file_path=temp_path,
            criminal_id=criminal_id,
            filename=f"embedding_{photo.filename}"
        )
        
        photo_url = None
        if storage_result:
            photo_url = storage_result['url']
            
            # Store photo metadata in suspect_photos table (non-fatal — FK may differ)
            try:
                database.store_suspect_photo(
                    criminal_id=criminal_id,
                    photo_url=photo_url,
                    photo_hash=file_hash,
                    embedding=face_analyzer.embedding_to_list(embedding),
                    face_confidence=confidence,
                    face_bbox=result.get('bbox'),
                    photo_quality='medium',
                    image_width=result.get('image_dimensions', {}).get('width', 0),
                    image_height=result.get('image_dimensions', {}).get('height', 0),
                    file_size_bytes=len(file_bytes),
                    is_primary=True
                )
            except Exception as sp_err:
                logger.warning(f"Could not store suspect_photo for {criminal_id} (non-fatal): {sp_err}")
        
        # Store the embedding on the criminal record itself (this is the critical one)
        database.update_criminal_embedding(
            criminal_id=criminal_id,
            embedding=face_analyzer.embedding_to_list(embedding),
            primary_photo_url=photo_url
        )
        
        logger.info(f"Embedding generated successfully for criminal {criminal_id}")
        
        return {
            "criminal_id": criminal_id,
            "has_embedding": True,
            "photos_processed": 1,
            "message": "Face embedding generated and stored successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding generation failed for {criminal_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Embedding generation failed: {str(e)}"
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {str(e)}")


@app.get("/criminals", response_model=List[CriminalInfo])
async def list_criminals():
    """
    List all registered criminals.
    
    Returns:
        List of criminals with basic info
    """
    try:
        criminals = database.get_all_criminals()
        
        result = []
        for c in criminals:
            result.append({
                "id": str(c['id']),
                "name": c.get('name', 'Unknown'),
                "nic": c.get('nic', ''),
                "risk_level": c.get('risk_level'),
                "primary_photo_url": c.get('primary_photo_url'),
                "status": c.get('status'),
                "has_embedding": False  # Will be set below
            })
        
        # Check which have embeddings
        criminals_with_embeddings = database.get_all_criminals_with_embeddings()
        embedding_ids = {str(c['id']) for c in criminals_with_embeddings}
        
        for r in result:
            r['has_embedding'] = r['id'] in embedding_ids
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list criminals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/criminals/{criminal_id}")
async def get_criminal(criminal_id: str):
    """
    Get details for a specific criminal.
    
    Args:
        criminal_id: Criminal ID
    
    Returns:
        Criminal details including photos
    """
    try:
        criminal = database.get_criminal_details(criminal_id)
        
        if not criminal:
            raise HTTPException(status_code=404, detail="Criminal not found")
        
        # Get photos
        photos = database.get_criminal_photos(criminal_id)
        
        return {
            "id": str(criminal['id']),
            "name": criminal.get('name'),
            "nic": criminal.get('nic'),
            "risk_level": criminal.get('risk_level'),
            "crime_history": criminal.get('crime_history'),
            "primary_photo_url": criminal.get('primary_photo_url'),
            "status": criminal.get('status'),
            "has_embedding": criminal.get('face_embedding') is not None,
            "photos": [{
                "photo_id": p.get('photo_id'),
                "url": p.get('photo_url'),
                "is_primary": p.get('is_primary'),
                "quality": p.get('photo_quality')
            } for p in photos]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get criminal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_analysis_history(
    user_id: Optional[str] = None,
    limit: int = Query(50, description="Maximum records to return")
):
    """
    Get facial recognition history/audit log.
    
    Args:
        user_id: Optional filter by user ID
        limit: Maximum records to return (default: 50)
    
    Returns:
        List of recognition history records
    """
    try:
        history = database.get_recognition_history(user_id=user_id, limit=limit)
        
        return {
            "count": len(history),
            "history": [{
                "log_id": h.get('log_id'),
                "face_detected": h.get('face_detected'),
                "face_quality": h.get('face_quality'),
                "matches_found": h.get('matches_found'),
                "best_match_criminal_id": h.get('best_match_criminal_id'),
                "best_match_similarity": h.get('best_match_similarity'),
                "processing_time_ms": h.get('processing_time_ms'),
                "requested_by": h.get('requested_by'),
                "case_id": h.get('case_id'),
                "created_at": str(h.get('created_at')) if h.get('created_at') else None
            } for h in history]
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
