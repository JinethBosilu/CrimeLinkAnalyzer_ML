# CrimeLinkAnalyzer ML Services

This repository contains Python-based machine learning microservices for the CrimeLinkAnalyzer application.

## Services

### 1. Call Analysis Service (Port 5001)
Analyzes call records from PDF files to identify patterns, build network graphs, and match against criminal database.

**Features:**
- PDF parsing with multiple format support
- Network graph generation using NetworkX
- Call pattern analysis (frequency, time patterns, common contacts)
- Criminal database matching
- Risk score calculation

**Endpoints:**
- `GET /health` - Health check
- `POST /analyze` - Upload PDF and analyze call records
- `GET /results/<analysis_id>` - Get analysis results
- `GET /results` - List all results

### 2. Facial Recognition Service (Port 5002)
*Coming soon - Will integrate with custom Asian face recognition model*

## Installation

### Prerequisites
- Python 3.9+
- pip
- PostgreSQL database access

### Setup

1. **Install dependencies:**
```bash
cd call_analysis_service
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. **Run the service:**
```bash
python app.py
```

The service will start on `http://localhost:5001`

## Testing

### Test Call Analysis
```bash
curl -X POST http://localhost:5001/analyze \
  -F "file=@sample_call_records.pdf"
```

### Check Health
```bash
curl http://localhost:5001/health
```

## PDF Format Support

The parser supports multiple call record formats:

**Format 1:**
```
2024-01-15 10:30:45 | +94771234567 | Outgoing | 00:05:23
```

**Format 2:**
```
15/01/2024 10:30 +94771234567 OUT 5m 23s
```

**Format 3:**
```
15-01-2024 10:30, +94771234567, Outgoing, 00:05:23
```

## Integration with Spring Boot

The Spring Boot backend calls these services via REST API:

```java
RestTemplate restTemplate = new RestTemplate();
String pythonServiceUrl = "http://localhost:5001/analyze";
ResponseEntity<Map> response = restTemplate.postForEntity(
    pythonServiceUrl, 
    fileData, 
    Map.class
);
```

## Database Schema

The service interacts with these tables:

### criminals
- id (VARCHAR PRIMARY KEY)
- name (VARCHAR)
- nic (VARCHAR)
- contact_number (VARCHAR)
- secondary_contact (VARCHAR)

### call_analysis_results
- id (VARCHAR PRIMARY KEY)
- file_name (VARCHAR)
- analysis_data (JSONB)
- risk_score (INTEGER)
- created_at (TIMESTAMP)

## Development

### Project Structure
```
call_analysis_service/
├── app.py                  # Flask application
├── requirements.txt        # Python dependencies
├── .env.example           # Environment configuration
├── uploads/               # Uploaded PDF files
├── results/               # Analysis results
└── utils/
    ├── pdf_parser.py      # PDF parsing logic
    ├── network_analyzer.py # Network graph analysis
    └── database.py        # Database operations
```

## Deployment

### Using Docker (Recommended)
```bash
docker build -t crimelink-call-analysis .
docker run -p 5001:5001 --env-file .env crimelink-call-analysis
```

### Production Considerations
- Use Redis for result caching instead of in-memory storage
- Implement rate limiting
- Add authentication/API keys
- Use Celery for async processing of large files
- Set up monitoring and logging
- Use environment-specific configurations

## License
Proprietary - Crime Link Analyzer System
