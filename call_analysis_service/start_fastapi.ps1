# CrimeLink Analyzer - Start ML Services (FastAPI)
# This script starts the FastAPI-based microservices

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "CrimeLink Analyzer - ML Services" -ForegroundColor Cyan
Write-Host "FastAPI Version 2.0.0" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to service directory
$servicePath = "d:\Project\Final Project\Project\Crimelink_Analyzer\CrimeLinkAnalyzer_ML\call_analysis_service"
Set-Location $servicePath

Write-Host "📁 Working directory: $servicePath" -ForegroundColor Yellow
Write-Host ""

# Check if FastAPI is installed
Write-Host "🔍 Checking dependencies..." -ForegroundColor Yellow
$fastApiInstalled = pip list | Select-String "fastapi"
if (-not $fastApiInstalled) {
    Write-Host "❌ FastAPI not found. Installing dependencies..." -ForegroundColor Red
    pip install -r requirements_fastapi.txt
    Write-Host "✅ Dependencies installed!" -ForegroundColor Green
} else {
    Write-Host "✅ FastAPI is installed" -ForegroundColor Green
}
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from example..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ .env created. Please configure database credentials." -ForegroundColor Green
    } else {
        Write-Host "❌ .env.example not found. Please create .env manually." -ForegroundColor Red
    }
    Write-Host ""
}

# Start the service
Write-Host "🚀 Starting FastAPI service..." -ForegroundColor Green
Write-Host ""
Write-Host "Service will be available at:" -ForegroundColor Cyan
Write-Host "  🌐 API: http://localhost:5001" -ForegroundColor White
Write-Host "  📚 Swagger Docs: http://localhost:5001/docs" -ForegroundColor White
Write-Host "  📖 ReDoc: http://localhost:5001/redoc" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the service" -ForegroundColor Yellow
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Start with uvicorn (using python -m to avoid PATH issues)
python -m uvicorn app_fastapi:app --host 0.0.0.0 --port 5001 --reload
