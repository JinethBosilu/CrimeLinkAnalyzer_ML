# =============================================
# CrimeLink Analyzer - Call Analysis Service
# Python FastAPI microservice
# =============================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (gcc for C extensions, curl for health checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app_fastapi.py .
COPY utils/ utils/

# Create uploads directory
RUN mkdir -p uploads

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

# Expose port
EXPOSE 5001

# Health check using curl (reliable, no Python import issues)
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app_fastapi:app", "--host", "0.0.0.0", "--port", "5001"]
