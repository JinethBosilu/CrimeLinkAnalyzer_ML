# Facial Recognition Service

Enterprise-grade facial recognition system for criminal identification using InsightFace and PostgreSQL.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd facial_recognition_service
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Verify Setup
```bash
python test_setup.py
```

### 3. Start Service
```bash
python app_facial.py
```

Service will run on: **http://localhost:5002**

### 4. Test Health
```bash
curl http://localhost:5002/health
```

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL database (Railway configured)
- InsightFace buffalo_sc models (✓ included)

## 🗄️ Database Setup

The database schema is already created. If you need to recreate:

```bash
psql -h centerbeam.proxy.rlwy.net -p 23821 -U postgres -d railway -f ../database/facial_recognition_tables.sql
```

## 📁 Project Structure

```
facial_recognition_service/
├── app_facial.py              # FastAPI application
├── requirements.txt           # Python dependencies
├── test_setup.py              # Setup verification script
├── .env                       # Configuration (configured)
├── QUICK_START.md             # Detailed documentation
├── utils/
│   ├── face_analyzer.py       # InsightFace wrapper
│   ├── database.py            # PostgreSQL operations
│   └── image_storage.py       # File handling
├── model/
│   └── models/
│       └── buffalo_sc/
│           ├── det_500m.onnx  ✓
│           └── w600k_mbf.onnx  ✓
├── uploads/                   # Temporary storage
└── suspect_images/            # Permanent storage
```

## 🔌 API Endpoints

### POST /analyze
Analyze suspect image and find matches.

**Example:**
```bash
curl -X POST http://localhost:5002/analyze \
  -F "image=@suspect.jpg" \
  -F "threshold=75"
```

**Response:**
```json
{
  "analysis_id": 1,
  "found_matches": true,
  "match_count": 1,
  "matches": [
    {
      "criminal_id": 1,
      "name": "John Doe",
      "nic": "123456789V",
      "similarity": 87.5,
      "confidence_level": "high"
    }
  ],
  "processing_time_ms": 650
}
```

### POST /register-criminal
Register new criminal with photos.

**Example:**
```bash
curl -X POST http://localhost:5002/register-criminal \
  -F "name=John Doe" \
  -F "nic=123456789V" \
  -F "risk_level=high" \
  -F "photos=@photo1.jpg" \
  -F "photos=@photo2.jpg"
```

### GET /health
Service health check.

### GET /history
Get recognition history.

## ⚙️ Configuration

`.env` file (already configured):

```env
DATABASE_URL=postgresql://postgres:...@centerbeam.proxy.rlwy.net:23821/railway
PORT=5002
DEFAULT_THRESHOLD=75
```

## 🎯 Similarity Thresholds

| Range   | Confidence | Use Case              |
|---------|------------|-----------------------|
| 85-100% | High       | Positive ID           |
| 75-85%  | Medium     | Needs verification    |
| 65-75%  | Low        | Potential lead        |
| <65%    | -          | Rejected              |

## 🔒 Security Features

- ✅ File type validation (JPG/PNG only)
- ✅ File size limits (5MB max)
- ✅ SHA-256 hash deduplication
- ✅ SQL injection protection
- ✅ Audit logging
- ✅ CORS configured

## 📊 Performance

Expected processing times:
- Face detection: ~200ms
- Embedding extraction: ~100ms
- Database comparison: ~100-400ms
- **Total: 500-800ms**

## 🧪 Testing

After starting the service, access the frontend:

**http://localhost:5173/investigator/facial-recognition**

1. Upload a suspect image
2. Adjust threshold (default 75%)
3. Click "Analyze Image"
4. View matches with crime history

## 🛠️ Troubleshooting

### ImportError: No module named 'xxx'
```bash
pip install -r requirements.txt
```

### No face detected
Ensure clear frontal face photo with good lighting. Minimum 80x80 pixels.

### Database connection failed
Check `.env` credentials and Railway connection.

### Model not found
Verify models in `model/models/buffalo_sc/`:
```bash
dir model\models\buffalo_sc
# Should show: det_500m.onnx, w600k_mbf.onnx
```

## 📚 Documentation

- **QUICK_START.md** - Comprehensive setup guide
- **FACIAL_RECOGNITION_IMPLEMENTATION.md** - Implementation details

## 🔄 Integration

### Frontend (Already Integrated)
- Component: `src/pages/Investigator/FacialRecognition.tsx`
- Features: Drag-drop upload, threshold adjustment, match display

### Backend (Optional Proxy)
Can add Spring Boot proxy at `/api/facial-recognition/*` if needed. Currently frontend calls Python service directly.

## 🚦 Status

✅ **Backend Service** - Complete and ready
✅ **Database Schema** - Deployed on Railway
✅ **Frontend Component** - Complete with full UI
✅ **InsightFace Models** - Copied and verified
✅ **Documentation** - Comprehensive guides

## 📞 Support

For issues:
1. Check `facial_recognition.log`
2. Run `python test_setup.py`
3. Verify `/health` endpoint
4. Check Railway database connection

---

**Built with:** FastAPI, InsightFace, PostgreSQL, React
**License:** MIT
**Version:** 1.0.0
