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
import uuid
from datetime import datetime
import logging
from pathlib import Path



# Import utilities
from utils.pdf_parser import parse_call_records
from utils.network_analyzer import analyze_call_network
from utils.database import get_criminal_info, store_analysis_result
from utils.session_manager import session_manager
from utils.location_analyzer import compute_location_periods

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app with metadata
app = FastAPI(
    title="CrimeLink Analyzer - ML Services",
    description="AI/ML Microservices for Crime Investigation Intelligence System",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # React frontend
        "http://localhost:8080",  # Spring Boot backend
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_FOLDER = Path("uploads")
RESULTS_FOLDER = Path("results")
UPLOAD_FOLDER.mkdir(exist_ok=True)
RESULTS_FOLDER.mkdir(exist_ok=True)

# In-memory storage (TODO: Replace with Redis for production)
analysis_results = {}

# File size limit (16MB)
MAX_FILE_SIZE = 16 * 1024 * 1024


# ============= Pydantic Models =============

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
    version: str


class AnalysisStartResponse(BaseModel):
    analysis_id: str
    status: str
    message: str


class CriminalMatch(BaseModel):
    phone: str
    criminal_id: str
    name: str
    nic: str
    crime_history: List[str] = Field(default_factory=list)

class LocationPeriod(BaseModel):
    location: str
    start: str
    end: str
    count: int

class LocationAnalysis(BaseModel):
    gap_minutes: int = 30
    locations: List[LocationPeriod] = Field(default_factory=list)



class AnalysisResult(BaseModel):
    """Complete analysis result for single PDF"""
    pdf_filename: str
    main_number: str
    total_calls: int
    total_incoming: int
    total_outgoing: int
    unique_numbers: List[str] = Field(default_factory=list)
    incoming_graph: Dict = Field(default_factory=dict)
    outgoing_graph: Dict = Field(default_factory=dict)
    call_frequency: Dict[str, int] = Field(default_factory=dict)
    time_pattern: Dict[str, int] = Field(default_factory=dict)
    common_contacts: List[Dict] = Field(default_factory=list)

    #  FIX: never missing now
    criminal_matches: List[CriminalMatch] = Field(default_factory=list)

    risk_score: int = Field(..., ge=0, le=100, description="Risk score (0-100)")
    location_analysis: LocationAnalysis = Field(default_factory=LocationAnalysis)


class BatchAnalysisResponse(BaseModel):
    session_id: str
    status: str
    message: str
    total_pdfs: int
    analyses: List[AnalysisResult]


class SessionAnalysisResponse(BaseModel):
    session_id: str
    total_analyses: int
    analyses: List[AnalysisResult]


class AnalysisListItem(BaseModel):
    analysis_id: str
    timestamp: str
    file_name: str
    status: str
    risk_score: Optional[int] = None


class AnalysisListResponse(BaseModel):
    total: int
    results: List[AnalysisListItem]


# ============= API Endpoints =============

@app.get("/", tags=["Root"])
async def root():
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
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
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
    tags=["Call Analysis"]
)
async def analyze_batch(files: List[UploadFile] = File(..., description="Multiple PDF files with call records")):
    """
    Analyze multiple call record PDFs in batch
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 PDFs per batch. Please split your upload.")

        # Create new session
        session_id = session_manager.create_session()
        logger.info(f"Created session {session_id} for batch analysis of {len(files)} PDFs")

        analyses: List[dict] = []

        for file in files:
            try:
                if not file.filename or not file.filename.lower().endswith(".pdf"):
                    logger.warning(f"Skipping non-PDF file: {file.filename}")
                    continue

                content = await file.read()

                if len(content) > MAX_FILE_SIZE:
                    logger.warning(f"Skipping {file.filename}: exceeds {MAX_FILE_SIZE/(1024*1024)}MB limit")
                    continue

                file_id = str(uuid.uuid4())
                file_path = UPLOAD_FOLDER / f"{file_id}.pdf"
                file_path.write_bytes(content)

                logger.info(f"Processing PDF: {file.filename}")

                call_records = parse_call_records(str(file_path))
                if not call_records:
                    logger.warning(f"No call records found in {file.filename}")
                    try:
                        file_path.unlink()
                    except:
                        pass
                    continue

                analysis = analyze_call_network(call_records)


                # Criminal matches
                criminal_matches = []
                for phone in analysis.get("unique_numbers", []):
                    criminal = get_criminal_info(phone)
                    if criminal:
                        criminal_matches.append({
                            "phone": phone,
                            "criminal_id": criminal.get("id", ""),
                            "name": criminal.get("name", ""),
                            "nic": criminal.get("nic", ""),
                            "crime_history": criminal.get("crimes", []) or []
                        })

                risk_score = calculate_risk_score(analysis, criminal_matches)

                location_analysis = compute_location_periods(call_records, gap_minutes=30)


                #  FIX: include criminal_matches always
                analysis_result = {
                    "pdf_filename": file.filename,
                    "main_number": analysis.get("main_number") or (call_records[0].get("main_number") if call_records else ""),
                    "total_calls": analysis.get("total_calls", 0),
                    "total_incoming": analysis.get("total_incoming", 0),
                    "total_outgoing": analysis.get("total_outgoing", 0),
                    "unique_numbers": analysis.get("unique_numbers", []),
                    "incoming_graph": analysis.get("incoming_graph", {}),
                    "outgoing_graph": analysis.get("outgoing_graph", {}),
                    "call_frequency": analysis.get("call_frequency", {}),
                    "time_pattern": analysis.get("time_pattern", {}),
                    "common_contacts": analysis.get("common_contacts", []),
                    "criminal_matches": criminal_matches,   #  REQUIRED FIELD
                    "risk_score": risk_score,
                    "location_analysis": location_analysis,
                    
                }

                analyses.append(analysis_result)
                

                try:
                    file_path.unlink()
                except:
                    pass

                logger.info(f"Completed analysis for {file.filename}")

            except Exception as e:
                logger.error(f"Error processing {file.filename}: {str(e)}", exc_info=True)
                continue

        if not analyses:
            raise HTTPException(status_code=400, detail="No valid call records found in any of the uploaded PDFs")

        for a in analyses:
            session_manager.add_analysis(session_id, a)

        return BatchAnalysisResponse(
            session_id=session_id,
            status="completed",
            message=f"Successfully analyzed {len(analyses)} PDF(s)",
            total_pdfs=len(analyses),
            analyses=analyses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")
    

@app.get(
    "/analysis/{session_id}",
    response_model=SessionAnalysisResponse,
    tags=["Call Analysis"]
)
async def get_session_analyses(session_id: str):
    analyses = session_manager.get_analyses(session_id)
    if analyses is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or has expired")

    return SessionAnalysisResponse(
        session_id=session_id,
        total_analyses=len(analyses),
        analyses=analyses
    )


@app.delete(
    "/analysis/{session_id}",
    tags=["Call Analysis"]
)
async def delete_session(session_id: str):
    success = session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"message": f"Session {session_id} deleted successfully"}


# ============= Helper Functions =============

def calculate_risk_score(analysis: dict, criminal_matches: list) -> int:
    score = 0

    total_calls = analysis.get("total_calls", 0)
    unique_numbers = analysis.get("unique_numbers", [])
    time_pattern = analysis.get("time_pattern", {}) or {}

    if total_calls > 100:
        score += 30
    elif total_calls > 50:
        score += 20

    score += len(criminal_matches) * 25

    if len(unique_numbers) > 50:
        score += 20

    late_night_calls = 0
    for hour, count in time_pattern.items():
        try:
            h = int(hour)
            if h >= 22 or h <= 5:
                late_night_calls += int(count)
        except:
            continue

    if total_calls > 0 and late_night_calls > total_calls * 0.3:
        score += 15

    return min(score, 100)


# ============= Exception Handlers =============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# ============= Startup/Shutdown Events =============

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("CrimeLink Analyzer - ML Services Starting...")
    logger.info("=" * 60)
    logger.info("Starting session cleanup thread (30 min timeout)...")
    session_manager.start_cleanup_thread()
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("CrimeLink Analyzer - ML Services Shutting Down...")
    session_manager.stop_cleanup_thread()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )
