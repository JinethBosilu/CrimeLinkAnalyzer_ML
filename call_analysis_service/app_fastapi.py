"""
CrimeLink Analyzer - Call Analysis Microservice (FastAPI)
Author: Group 05
Date: November 30, 2025

This microservice handles:
- PDF call record parsing
- Communication network analysis
- Criminal database matching
- Risk score calculation

Future services to be added:
- Facial recognition (UC-102)
- Crime hotspot analysis (UC-103)
- Predictive crime modeling
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import os
import uuid
from datetime import datetime
import logging
from pathlib import Path

# Import utilities
from utils.pdf_parser import parse_call_records
from utils.network_analyzer import analyze_call_network
from utils.database import get_criminal_info
from utils.session_manager import session_manager
from utils.location_analyzer import compute_location_periods

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app with metadata
app = FastAPI(
    title="CrimeLink Analyzer - ML Services",
    description="AI/ML Microservices for Crime Investigation Intelligence System",
    version="2.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc UI
)

# CORS Configuration - read from environment variable
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

# Configuration
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)

# File size limit (16MB)
MAX_FILE_SIZE = 16 * 1024 * 1024


# ============= Pydantic Models (Request/Response Validation) =============

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="API version")


class CriminalMatch(BaseModel):
    """Criminal match information"""
    phone: str
    criminal_id: str
    name: str
    nic: str
    crime_history: List[str]


class LocationPeriod(BaseModel):
    """Cell tower location with time period"""
    location: str
    start: str
    end: str
    count: int


class LocationAnalysis(BaseModel):
    """Location analysis result"""
    gap_minutes: int = 180
    locations: List[LocationPeriod] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Complete analysis result for single PDF"""
    pdf_filename: str
    main_number: str
    total_calls: int
    total_incoming: int
    total_outgoing: int
    unique_numbers: List[str]
    incoming_graph: Dict
    outgoing_graph: Dict
    call_frequency: Dict[str, int]
    time_pattern: Dict[str, int]
    common_contacts: List[Dict]
    criminal_matches: List[CriminalMatch]
    risk_score: int = Field(..., ge=0, le=100, description="Risk score (0-100)")
    location_analysis: LocationAnalysis = Field(default_factory=LocationAnalysis)
    
    class Config:
        arbitrary_types_allowed = True


class BatchAnalysisResponse(BaseModel):
    """Response for batch analysis"""
    session_id: str
    status: str
    message: str
    total_pdfs: int
    analyses: List[AnalysisResult]
    
    class Config:
        arbitrary_types_allowed = True


class SessionAnalysisResponse(BaseModel):
    """Response when retrieving session analyses"""
    session_id: str
    total_analyses: int
    analyses: List[AnalysisResult]
    
    class Config:
        arbitrary_types_allowed = True


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None


# ============= API Endpoints =============

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "service": "CrimeLink Analyzer - ML Services",
        "version": "2.0.0",
        "status": "operational",
        "documentation": "/docs",
        "endpoints": {
            "health": "/health",
            "batch_analysis": "/analyze/batch",
            "session_analysis": "/analysis/{session_id}",
            "delete_session": "/analysis/{session_id}"
        },
        "features": {
            "separate_incoming_outgoing_graphs": True,
            "multi_pdf_support": True,
            "session_based_storage": True,
            "auto_cleanup_30_min": True
        },
        "future_services": [
            "Facial Recognition (UC-102)",
            "Crime Hotspot Analysis (UC-103)",
            "Predictive Crime Modeling"
        ]
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns service status and version information
    """
    logger.info("Health check requested")
    return HealthResponse(
        status="healthy",
        service="call_analysis_service",
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.0"
    )


@app.post(
    "/analyze/batch",
    response_model=BatchAnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Call Analysis"],
    summary="Analyze multiple call record PDFs",
    description="""
    Upload multiple PDF files for batch analysis with session-based storage.
    
    **Process:**
    1. Creates a new session
    2. Processes each PDF separately
    3. Generates incoming and outgoing graphs per PDF
    4. Returns session_id to retrieve results later
    
    **Features:**
    - Multi-PDF upload support
    - Separate incoming/outgoing network graphs
    - Session expires after 30 minutes of inactivity
    - No persistent storage (memory only)
    
    **Returns:** Session ID and all analysis results
    """
)
async def analyze_batch(files: List[UploadFile] = File(..., description="Multiple PDF files with call records")):
    """
    Analyze multiple call record PDFs in batch
    
    **UC-101: Enhanced Call Record Analysis with Dual Graphs**
    """
    try:
        # Validate files
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )
        
        if len(files) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 PDFs per batch. Please split your upload."
            )
        
        # Create new session
        session_id = session_manager.create_session()
        logger.info(f"Created session {session_id} for batch analysis of {len(files)} PDFs")
        
        analyses = []
        
        # Process each PDF
        for file in files:
            try:
                # Validate file type
                if not file.filename or not file.filename.lower().endswith('.pdf'):
                    logger.warning(f"Skipping non-PDF file: {file.filename}")
                    continue
                
                # Read file content
                content = await file.read()
                
                # Check file size (16MB limit per file)
                if len(content) > MAX_FILE_SIZE:
                    logger.warning(f"Skipping {file.filename}: exceeds {MAX_FILE_SIZE / (1024*1024)}MB limit")
                    continue
                
                # Save uploaded file
                file_id = str(uuid.uuid4())
                file_path = UPLOAD_FOLDER / f"{file_id}.pdf"
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"Processing PDF: {file.filename}")
                
                # Parse call records
                call_records = parse_call_records(str(file_path))
                
                if not call_records:
                    logger.warning(f"No call records found in {file.filename}")
                    continue
                
                logger.info(f"Found {len(call_records)} call records in {file.filename}")
                
                # Analyze call network (now returns separate incoming/outgoing graphs)
                analysis = analyze_call_network(call_records)
                
                # Check for criminal matches
                criminal_matches = []
                for phone in analysis['unique_numbers']:
                    criminal = get_criminal_info(phone)
                    if criminal:
                        criminal_matches.append({
                            'phone': phone,
                            'criminal_id': criminal['id'],
                            'name': criminal['name'],
                            'nic': criminal['nic'],
                            'crime_history': criminal['crimes']
                        })
                
                # Calculate risk score
                risk_score = calculate_risk_score(analysis, criminal_matches)
                
                # Compute location periods from call records
                location_analysis = compute_location_periods(call_records, gap_minutes=180)
                
                # Prepare analysis result
                analysis_result = {
                    'pdf_filename': file.filename,
                    'main_number': analysis['main_number'],
                    'total_calls': analysis['total_calls'],
                    'total_incoming': analysis['total_incoming'],
                    'total_outgoing': analysis['total_outgoing'],
                    'unique_numbers': analysis['unique_numbers'],
                    'incoming_graph': analysis['incoming_graph'],
                    'outgoing_graph': analysis['outgoing_graph'],
                    'call_frequency': analysis['call_frequency'],
                    'time_pattern': analysis['time_pattern'],
                    'common_contacts': analysis['common_contacts'],
                    'criminal_matches': criminal_matches,
                    'risk_score': risk_score,
                    'location_analysis': location_analysis
                }
                
                analyses.append(analysis_result)
                
                # Cleanup uploaded file
                try:
                    file_path.unlink()
                except:
                    pass
                
                logger.info(f"Completed analysis for {file.filename}")
                
            except Exception as e:
                logger.error(f"Error processing {file.filename}: {str(e)}")
                continue
        
        if not analyses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid call records found in any of the uploaded PDFs"
            )
        
        # Store analyses in session
        for analysis in analyses:
            session_manager.add_analysis(session_id, analysis)
        
        logger.info(f"Session {session_id}: Completed batch analysis of {len(analyses)} PDFs")
        
        return BatchAnalysisResponse(
            session_id=session_id,
            status='completed',
            message=f'Successfully analyzed {len(analyses)} PDF(s)',
            total_pdfs=len(analyses),
            analyses=analyses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch analysis failed: {str(e)}"
        )


@app.get(
    "/analysis/{session_id}",
    response_model=SessionAnalysisResponse,
    tags=["Call Analysis"],
    summary="Get all analyses for a session",
    description="Retrieve all analysis results stored in a session"
)
async def get_session_analyses(session_id: str):
    """
    Get all analyses for a session
    
    Returns all PDF analyses associated with the session.
    Session expires after 30 minutes of inactivity.
    """
    logger.info(f"Retrieving analyses for session: {session_id}")
    
    analyses = session_manager.get_analyses(session_id)
    
    if analyses is None:
        logger.warning(f"Session not found or expired: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or has expired"
        )
    
    return SessionAnalysisResponse(
        session_id=session_id,
        total_analyses=len(analyses),
        analyses=analyses
    )


@app.delete(
    "/analysis/{session_id}",
    tags=["Call Analysis"],
    summary="Delete session",
    description="Remove session and all associated analyses (on logout)"
)
async def delete_session(session_id: str):
    """
    Delete session and all analyses (called on investigator logout)
    """
    success = session_manager.delete_session(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found"
        )
    
    logger.info(f"Deleted session: {session_id}")
    
    return {"message": f"Session {session_id} deleted successfully"}


# ============= Helper Functions =============

def calculate_risk_score(analysis: dict, criminal_matches: list) -> int:
    """
    Calculate risk score based on analysis patterns
    
    Risk factors:
    - Call volume (20-30 points)
    - Criminal connections (25 points each)
    - Contact diversity (20 points)
    - Unusual time patterns (15 points)
    
    Returns:
        int: Risk score between 0-100
    """
    score = 0
    
    # High number of calls increases risk
    if analysis['total_calls'] > 100:
        score += 30
    elif analysis['total_calls'] > 50:
        score += 20
    
    # Criminal matches significantly increase risk
    score += len(criminal_matches) * 25
    
    # Many unique contacts increase risk
    if len(analysis['unique_numbers']) > 50:
        score += 20
    
    # Unusual time patterns (late night calls 10pm-5am)
    late_night_calls = sum(
        count for hour, count in analysis['time_pattern'].items()
        if int(hour) >= 22 or int(hour) <= 5
    )
    if analysis['total_calls'] > 0 and late_night_calls > analysis['total_calls'] * 0.3:
        score += 15
    
    return min(score, 100)  # Cap at 100


# ============= Exception Handlers =============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# ============= Startup/Shutdown Events =============

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("=" * 60)
    logger.info("CrimeLink Analyzer - ML Services Starting...")
    logger.info("=" * 60)
    logger.info(f"Version: 2.0.0")
    logger.info(f"Upload folder: {UPLOAD_FOLDER.absolute()}")
    logger.info(f"API Documentation: http://0.0.0.0:{os.environ.get('PORT', '5001')}/docs")
    logger.info("Starting session cleanup thread (30 min timeout)...")
    session_manager.start_cleanup_thread()
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("CrimeLink Analyzer - ML Services Shutting Down...")
    logger.info("Stopping session cleanup thread...")
    session_manager.stop_cleanup_thread()
    logger.info("Shutdown complete")


# ============= Run Server =============

if __name__ == '__main__':
    import uvicorn
    
    port = int(os.environ.get("PORT", 5001))
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("FASTAPI_ENV", "development") == "development",
        log_level="info"
    )
