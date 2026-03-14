# =============================================
# CrimeLink Analyzer - Facial Recognition Service
# Python FastAPI + InsightFace / ONNX Runtime
# =============================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by OpenCV, InsightFace, and health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app_facial.py .
COPY utils/ utils/

# Copy InsightFace model weights (buffalo_sc ~16MB)
COPY model/ model/

# Create working directories
RUN mkdir -p uploads suspect_images

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

# Expose port
EXPOSE 5002

# Health check using curl (reliable, no Python import issues)
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app_facial:app", "--host", "0.0.0.0", "--port", "5002"]
