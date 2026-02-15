# 🔍 Facial Recognition Service - Quick Start

**FastAPI service for criminal face recognition using InsightFace + Supabase**

---

## ⚡ Quick Start

```powershell
# Navigate to service
cd "d:\Project\Final Project\Project\Crimelink_Analyzer\CrimeLinkAnalyzer_ML\facial_recognition_service"

# Start service (port 5002)
python -m uvicorn app_facial:app --host 0.0.0.0 --port 5002
```

**Done!** Open: http://localhost:5002/docs

---

## 📚 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - service status |
| `/criminals` | GET | List all registered criminals |
| `/criminals/{id}` | GET | Get criminal details + photos |
| `/analyze` | POST | Analyze suspect image, find matches |
| `/register` | POST | Register new criminal with photos |
| `/history` | GET | Get facial recognition audit logs |

---

## 🎯 Key Features

- **InsightFace buffalo_sc** - 512-dimensional face embeddings
- **Supabase Storage** - Cloud image storage for criminal photos
- **Supabase PostgreSQL** - Shared database with Spring Boot backend
- **Audit Logging** - All recognition requests logged
- **Multi-photo averaging** - Better accuracy with multiple photos per criminal

---

## 📋 Example: Analyze Suspect Image

```bash
curl -X POST "http://localhost:5002/analyze" \
  -F "image=@suspect.jpg" \
  -F "threshold=45"
```

**Response:**
```json
{
  "analysis_id": 1,
  "found_matches": true,
  "match_count": 1,
  "matches": [
    {
      "criminal_id": "4",
      "name": "Mahinda Rajapaksa",
      "similarity": 87.5,
      "confidence_level": "high",
      "photo_url": "https://..."
    }
  ],
  "face_quality": "high",
  "processing_time_ms": 245.5
}
```

---

## 🔧 Configuration

Environment variables in `.env`:
```env
DATABASE_URL=postgresql://...@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_xxx
SUPABASE_BUCKET=criminal-photos
```

---

## 🏗️ Architecture

```
facial_recognition_service/
├── app_facial.py          # FastAPI application
├── requirements.txt       # Python dependencies
├── .env                   # Supabase credentials
├── model/
│   └── models/
│       └── buffalo_sc/    # InsightFace ONNX models
│           ├── det_500m.onnx
│           └── w600k_mbf.onnx
└── utils/
    ├── face_analyzer.py   # Face detection & embedding
    ├── database.py        # Supabase PostgreSQL
    └── supabase_storage.py # Supabase Storage
```

---

## ✅ Verify Service

```powershell
# Check health
(Invoke-WebRequest -Uri "http://localhost:5002/health" -UseBasicParsing).Content

# List criminals
(Invoke-WebRequest -Uri "http://localhost:5002/criminals" -UseBasicParsing).Content
```

---

**Service is ready!** 🚀
