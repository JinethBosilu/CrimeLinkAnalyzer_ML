# Upload Criminal Data - Guide

## Method 1: Using Upload Script (Easiest)

### Step 1: Start the Service
```bash
cd facial_recognition_service
venv\Scripts\activate
python app_facial.py
```

### Step 2: Run Upload Script
```bash
# In another terminal (service must be running)
python upload_test_data.py
```

This script will upload 4 test criminals with sample crime histories.

## Method 2: Using API Directly

### PowerShell Example
```powershell
# Start service first
cd facial_recognition_service
venv\Scripts\activate
python app_facial.py

# In another PowerShell (with photo)
Invoke-WebRequest -Uri "http://localhost:5002/register-criminal" `
  -Method POST `
  -Form @{
    name = "Kasun Perera"
    nic = "199012345678"
    risk_level = "high"
    crime_history = '{"total_crimes": 3, "last_crime_date": "2024-12-01", "crime_types": ["theft", "assault"]}'
    photos = Get-Item "path\to\photo.jpg"
  }
```

### Python Example
```python
import requests

files = {'photos': open('photo.jpg', 'rb')}
data = {
    'name': 'Kasun Perera',
    'nic': '199012345678',
    'risk_level': 'high',
    'crime_history': '{"total_crimes": 3, "crime_types": ["theft"]}'
}

response = requests.post(
    'http://localhost:5002/register-criminal',
    data=data,
    files=files
)
print(response.json())
```

## Method 3: Bulk Upload from Folder

### Step 1: Create Folder Structure
```
test_data/
  ├── criminal_1/
  │   ├── info.json
  │   ├── photo1.jpg
  │   └── photo2.jpg
  ├── criminal_2/
  │   ├── info.json
  │   └── photo1.jpg
```

### Step 2: Create info.json for Each Criminal
```json
{
  "name": "Kasun Perera",
  "nic": "199012345678",
  "risk_level": "high",
  "crime_history": {
    "total_crimes": 3,
    "last_crime_date": "2024-12-01",
    "crime_types": ["armed robbery", "assault"],
    "records": [
      {
        "type": "Armed Robbery",
        "date": "2024-12-01",
        "location": "Colombo",
        "description": "Bank robbery with weapons"
      }
    ]
  }
}
```

### Step 3: Run Bulk Upload
```bash
python bulk_upload_from_folder.py test_data/
```

## Method 4: Direct SQL Insert

If you need to insert without photos (not recommended):

```sql
-- Connect to database
psql -h centerbeam.proxy.rlwy.net -p 23821 -U postgres -d railway

-- Insert criminal
INSERT INTO criminals (name, nic, crime_history, risk_level, status)
VALUES (
  'Kasun Perera',
  '199012345678',
  '{"total_crimes": 3, "crime_types": ["theft", "assault"]}'::jsonb,
  'high',
  'active'
);
```

**Note:** SQL insert won't include face embeddings, so facial recognition won't work!

## Field Reference

### Required Fields
- `name` - Full name (string)
- `nic` - National Identity Card number (string)
- `photos` - At least 1 photo (file)

### Optional Fields
- `risk_level` - One of: low, medium, high, critical (default: medium)
- `crime_history` - JSON object with:
  - `total_crimes` - Number
  - `last_crime_date` - ISO date string
  - `crime_types` - Array of strings
  - `records` - Array of crime record objects

### Crime Record Object
```json
{
  "type": "Armed Robbery",
  "date": "2024-12-01",
  "location": "Colombo Fort",
  "description": "Bank robbery details"
}
```

## Tips

1. **Photo Quality**: Use clear frontal face photos with good lighting
2. **Multiple Photos**: Use 2-3 photos per criminal for better accuracy
3. **Photo Format**: JPG or PNG, max 5MB each
4. **NIC Format**: Must be unique per criminal

## Troubleshooting

### "Service not running"
Start the service:
```bash
cd facial_recognition_service
venv\Scripts\activate
python app_facial.py
```

### "No face detected"
- Ensure photo has clear frontal face
- Check lighting and photo quality
- Minimum face size: 80x80 pixels

### "At least one photo required"
You must provide at least 1 photo for facial recognition to work.

## Example: Quick Test Upload

```bash
# 1. Start service
cd facial_recognition_service
venv\Scripts\activate
python app_facial.py

# 2. In another terminal, run test upload
python upload_test_data.py

# 3. Check results
curl http://localhost:5002/history
```
