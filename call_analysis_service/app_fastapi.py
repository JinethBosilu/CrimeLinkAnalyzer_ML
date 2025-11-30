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
from utils.database import get_criminal_info, store_analysis_result

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

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # React frontend
        "http://localhost:8080",  # Spring Boot backend
        "http://localhost:3000"   # Alternative frontend port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_FOLDER = Path('uploads')
RESULTS_FOLDER = Path('results')
UPLOAD_FOLDER.mkdir(exist_ok=True)
RESULTS_FOLDER.mkdir(exist_ok=True)

# In-memory storage (TODO: Replace with Redis for production)
analysis_results = {}

# File size limit (16MB)
MAX_FILE_SIZE = 16 * 1024 * 1024


# ============= Pydantic Models (Request/Response Validation) =============

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="API version")


class AnalysisStartResponse(BaseModel):
    """Response when analysis is initiated"""
    analysis_id: str = Field(..., description="Unique analysis identifier")
    status: str = Field(..., description="Analysis status")
    message: str = Field(..., description="Status message")


class CriminalMatch(BaseModel):
    """Criminal match information"""
    phone: str
    criminal_id: str
    name: str
    nic: str
    crime_history: List[str]


class NetworkGraph(BaseModel):
    """Network graph structure"""
    nodes: int
    edges: int
    density: float
    avg_degree: float
    centrality: Dict[str, float]
    
    class Config:
        arbitrary_types_allowed = True


class AnalysisResult(BaseModel):
    """Complete analysis result"""
    analysis_id: str
    status: str
    timestamp: str
    file_name: str
    total_calls: int
    unique_numbers: List[str]
    call_frequency: Dict[str, int]
    time_pattern: Dict[str, int]
    common_contacts: List[Dict]
    network_graph: Dict
    criminal_matches: List[CriminalMatch]
    risk_score: int = Field(..., ge=0, le=100, description="Risk score (0-100)")
    
    class Config:
        arbitrary_types_allowed = True


class AnalysisListItem(BaseModel):
    """Summary item for analysis list"""
    analysis_id: str
    timestamp: str
    file_name: str
    status: str
    risk_score: Optional[int] = None


class AnalysisListResponse(BaseModel):
    """Response for listing all analyses"""
    total: int
    results: List[AnalysisListItem]


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    analysis_id: Optional[str] = None


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
            "call_analysis": "/analyze",
            "results": "/results/{analysis_id}",
            "list_all": "/results"
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
    "/analyze",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_200_OK,
    tags=["Call Analysis"],
    summary="Analyze call records from PDF",
    description="""
    Upload a PDF file containing call records for analysis.
    
    **Process:**
    1. Parse PDF to extract call records
    2. Build communication network graph
    3. Check numbers against criminal database
    4. Calculate risk score based on patterns
    
    **Supported PDF formats:**
    - Standard call log format
    - Telecom provider formats
    - Custom formatted records
    
    **Returns:** Analysis ID for retrieving results
    """
)
async def analyze_call_records(file: UploadFile = File(..., description="PDF file with call records")):
    """
    Analyze call records from uploaded PDF file
    
    **UC-101: Call Record Linkage Analysis**
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file selected"
            )
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported. Please upload a .pdf file."
            )
        
        # Check file size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE / (1024*1024)}MB"
            )
        
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        logger.info(f"Starting analysis {analysis_id} for file: {file.filename}")
        
        # Save uploaded file
        file_path = UPLOAD_FOLDER / f"{analysis_id}.pdf"
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Parse call records from PDF
        logger.info(f"Parsing PDF: {file.filename}")
        call_records = parse_call_records(str(file_path))
        
        if not call_records:
            logger.warning(f"No call records found in {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No call records found in PDF. Please ensure the file contains valid call data."
            )
        
        logger.info(f"Found {len(call_records)} call records")
        
        # Analyze call network
        logger.info("Analyzing communication network...")
        analysis = analyze_call_network(call_records)
        
        # Check if any numbers belong to criminals in database
        logger.info("Checking for criminal matches...")
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
        
        logger.info(f"Found {len(criminal_matches)} criminal matches")
        
        # Calculate risk score
        risk_score = calculate_risk_score(analysis, criminal_matches)
        logger.info(f"Risk score calculated: {risk_score}")
        
        # Prepare result
        result = {
            'analysis_id': analysis_id,
            'status': 'completed',
            'timestamp': datetime.utcnow().isoformat(),
            'file_name': file.filename,
            'total_calls': analysis['total_calls'],
            'unique_numbers': analysis['unique_numbers'],
            'call_frequency': analysis['call_frequency'],
            'time_pattern': analysis['time_pattern'],
            'common_contacts': analysis['common_contacts'],
            'network_graph': analysis['network_graph'],
            'criminal_matches': criminal_matches,
            'risk_score': risk_score
        }
        
        # Store result in memory (TODO: Use Redis)
        analysis_results[analysis_id] = result
        
        # Store in database
        try:
            store_analysis_result(analysis_id, result)
            logger.info(f"Analysis {analysis_id} stored successfully")
        except Exception as db_error:
            logger.error(f"Database storage failed: {str(db_error)}")
            # Continue even if DB storage fails
        
        return AnalysisStartResponse(
            analysis_id=analysis_id,
            status='completed',
            message='Analysis completed successfully'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@app.get(
    "/results/{analysis_id}",
    response_model=AnalysisResult,
    tags=["Call Analysis"],
    summary="Get analysis results by ID",
    description="Retrieve the complete analysis results for a given analysis ID"
)
async def get_analysis_results(analysis_id: str):
    """
    Get analysis results by ID
    
    Returns complete analysis including:
    - Call statistics
    - Network graph metrics
    - Criminal matches
    - Risk assessment
    """
    logger.info(f"Retrieving results for analysis: {analysis_id}")
    
    if analysis_id not in analysis_results:
        logger.warning(f"Analysis not found: {analysis_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID '{analysis_id}' not found"
        )
    
    return analysis_results[analysis_id]


@app.get(
    "/results",
    response_model=AnalysisListResponse,
    tags=["Call Analysis"],
    summary="List all analyses",
    description="Get a list of all completed analyses (for testing and monitoring)"
)
async def list_all_results():
    """
    List all analysis results
    
    Useful for:
    - Monitoring active analyses
    - Testing API functionality
    - Admin dashboard
    """
    logger.info(f"Listing all results. Total: {len(analysis_results)}")
    
    results_list = [
        AnalysisListItem(
            analysis_id=aid,
            timestamp=result['timestamp'],
            file_name=result['file_name'],
            status=result['status'],
            risk_score=result.get('risk_score')
        )
        for aid, result in analysis_results.items()
    ]
    
    return AnalysisListResponse(
        total=len(analysis_results),
        results=results_list
    )


@app.delete(
    "/results/{analysis_id}",
    tags=["Call Analysis"],
    summary="Delete analysis results",
    description="Remove analysis results from memory (admin only)"
)
async def delete_analysis(analysis_id: str):
    """Delete analysis results (for cleanup/testing)"""
    if analysis_id not in analysis_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID '{analysis_id}' not found"
        )
    
    del analysis_results[analysis_id]
    logger.info(f"Deleted analysis: {analysis_id}")
    
    return {"message": f"Analysis {analysis_id} deleted successfully"}


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
    logger.info(f"Results folder: {RESULTS_FOLDER.absolute()}")
    logger.info("API Documentation: http://localhost:5001/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("CrimeLink Analyzer - ML Services Shutting Down...")
    # TODO: Close database connections, Redis, etc.


# ============= Run Server =============

if __name__ == '__main__':
    import uvicorn
    
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=5001,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )
