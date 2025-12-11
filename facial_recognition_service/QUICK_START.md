# Facial Recognition Service - Quick Start Guide

## Overview
Enterprise facial recognition system using InsightFace buffalo_sc model for criminal identification.

## Architecture
```
React Frontend → Spring Boot → FastAPI (Python) → PostgreSQL
```

## Prerequisites
- Python 3.9+
- PostgreSQL database (Railway)
- InsightFace buffalo_sc model (✓ already copied)

## Setup

### 1. Install Dependencies
```bash
cd facial_recognition_service
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 2. Database Setup
```bash
# Run the SQL schema in PostgreSQL
psql -h centerbeam.proxy.rlwy.net -p 23821 -U postgres -d railway < ../database/facial_recognition_tables.sql
```

Or connect manually and run:
```sql
-- Creates tables: criminals, suspect_photos, facial_recognition_logs
-- See database/facial_recognition_tables.sql for full schema
```

### 3. Environment Configuration
Copy `.env.example` to `.env` (already configured with Railway credentials):
```env
DATABASE_URL=postgresql://postgres:...@centerbeam.proxy.rlwy.net:23821/railway
PORT=5002
DEFAULT_THRESHOLD=75
```

### 4. Verify Model Files
Check that InsightFace models are in place:
```
facial_recognition_service/
└── model/
    └── models/
        └── buffalo_sc/
            ├── det_500m.onnx  ✓
            └── w600k_mbf.onnx  ✓
```

### 5. Start Service
```bash
cd facial_recognition_service
venv\Scripts\activate
python app_facial.py
```

Server runs on: http://localhost:5002

## API Endpoints

### POST /analyze
Analyze suspect image and find matches.

**Request:**
```bash
curl -X POST http://localhost:5002/analyze \
  -F "image=@suspect.jpg" \
  -F "threshold=75" \
  -F "user_id=investigator123"
```

**Response:**
```json
{
  "analysis_id": 1,
  "found_matches": true,
  "match_count": 2,
  "matches": [
    {
      "criminal_id": 1,
      "name": "John Doe",
      "nic": "123456789V",
      "similarity": 87.5,
      "confidence_level": "high",
      "crime_history": {...},
      "risk_level": "high"
    }
  ],
  "processing_time_ms": 650,
  "timestamp": "2024-01-15T10:30:00"
}
```

### POST /register-criminal
Register new criminal with photos.

**Request:**
```bash
curl -X POST http://localhost:5002/register-criminal \
  -F "name=John Doe" \
  -F "nic=123456789V" \
  -F "risk_level=high" \
  -F 'crime_history={"total_crimes": 3, "crime_types": ["theft", "assault"]}' \
  -F "photos=@photo1.jpg" \
  -F "photos=@photo2.jpg" \
  -F "user_id=admin"
```

**Response:**
```json
{
  "criminal_id": 1,
  "name": "John Doe",
  "nic": "123456789V",
  "photos_stored": 2,
  "embedding_quality": "high",
  "message": "Successfully registered with 2 photo(s)"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "services": {
    "database": "ok",
    "face_analyzer": "ok",
    "storage": "ok"
  }
}
```

### GET /history
Get recognition history.

**Request:**
```bash
curl http://localhost:5002/history?user_id=investigator123&limit=50
```

## Database Schema

### criminals
- `id`, `name`, `nic`, `face_embedding` (BYTEA)
- `crime_history` (JSONB), `risk_level`, `status`
- `embedding_quality`, `photo_count`

### suspect_photos
- `id`, `criminal_id`, `image_path`, `file_hash`
- `embedding` (BYTEA), `quality`, `is_primary`
- `bbox_x`, `bbox_y`, `width`, `height`

### facial_recognition_logs
- `id`, `suspect_image_hash`, `matches_found`
- `top_match_id`, `similarity_score`
- `processing_time_ms`, `user_id`, `ip_address`

## Similarity Thresholds

| Threshold | Confidence | Use Case |
|-----------|------------|----------|
| 85-100%   | High       | Positive identification |
| 75-85%    | Medium     | Requires verification |
| 65-75%    | Low        | Potential lead |
| <65%      | -          | Rejected (not returned) |

## Frontend Integration

The FacialRecognition.tsx component is already configured:
```typescript
// Upload image → http://localhost:5002/analyze
// Display matches with similarity percentage
// Show crime history and risk levels
```

Access at: http://localhost:5173/investigator/facial-recognition

## Performance Metrics

Expected processing times:
- Face detection: ~200ms
- Embedding extraction: ~100ms
- Database comparison: ~100-400ms (depends on database size)
- **Total: 500-800ms per request**

## Troubleshooting

### Issue: Import errors (psycopg, insightface)
**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Issue: No face detected
**Solution:** Ensure clear frontal face photo with good lighting. Minimum face size: 80x80 pixels.

### Issue: Database connection failed
**Solution:** Check `.env` credentials and Railway connection:
```bash
psql postgresql://postgres:...@centerbeam.proxy.rlwy.net:23821/railway
```

### Issue: Model not found
**Solution:** Verify models in `model/models/buffalo_sc/`:
```bash
ls model/models/buffalo_sc/
# Should show: det_500m.onnx, w600k_mbf.onnx
```

## Directory Structure

```
facial_recognition_service/
├── app_facial.py           # Main FastAPI application
├── requirements.txt        # Python dependencies
├── .env                    # Configuration (Railway credentials)
├── .env.example            # Configuration template
├── utils/
│   ├── __init__.py
│   ├── face_analyzer.py    # InsightFace wrapper
│   ├── database.py         # PostgreSQL operations
│   └── image_storage.py    # File handling
├── model/
│   └── models/
│       └── buffalo_sc/     # InsightFace ONNX models
├── uploads/                # Temporary uploads
└── suspect_images/         # Permanent storage (organized by criminal_id)
```

## Security Features

✓ File type validation (JPG/PNG only)
✓ File size limits (5MB max)
✓ SHA-256 hash for duplicate prevention
✓ SQL injection protection (prepared statements)
✓ Audit logging (all requests logged)
✓ JWT authentication support
✓ CORS configuration

## Production Deployment

1. Set `LOG_LEVEL=WARNING` in .env
2. Disable debug mode in uvicorn
3. Configure nginx/Apache reverse proxy
4. Set up SSL certificates
5. Enable rate limiting
6. Configure backup for suspect_images/
7. Monitor PostgreSQL performance

## Support

For issues or questions:
- Check logs: `facial_recognition.log`
- Verify service health: http://localhost:5002/health
- Review database logs in Railway dashboard
