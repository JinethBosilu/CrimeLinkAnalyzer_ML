# 🚀 Quick Start - CrimeLink Analyzer ML Service

**Get running in 2 minutes!**

---

## ⚡ Super Quick Start

```powershell
# 1. Navigate to service
cd "d:\Project\Final Project\Project\Crimelink_Analyzer\CrimeLinkAnalyzer_ML\call_analysis_service"

# 2. Install dependencies (first time only)
pip install -r requirements_fastapi.txt

# 3. Start service

cd 
```

**Done!** Open: http://localhost:5001/docs

---

## 📋 Copy-Paste Commands

### Windows PowerShell:
```powershell
cd "d:\Project\Final Project\Project\Crimelink_Analyzer\CrimeLinkAnalyzer_ML\call_analysis_service" ; python -m uvicorn app_fastapi:app --host 0.0.0.0 --port 5001 --reload
```

### First Time Setup (One Command):
```powershell
cd "d:\Project\Final Project\Project\Crimelink_Analyzer\CrimeLinkAnalyzer_ML\call_analysis_service" ; pip install -r requirements_fastapi.txt ; python -m uvicorn app_fastapi:app --host 0.0.0.0 --port 5001 --reload
```

---

## ✅ Verify It's Working

Open in browser: **http://localhost:5001/docs**

You should see the interactive Swagger UI! 🎉

---

## 🛑 Stop Service

Press **Ctrl+C** in terminal

---

## 🐛 Common Issues

### "Module not found"
```powershell
pip install -r requirements_fastapi.txt
```

### "Port already in use"
```powershell
# Use different port
python -m uvicorn app_fastapi:app --port 5002 --reload
```

### "Can't find uvicorn"
```powershell
# Use python -m (always works)
python -m uvicorn app_fastapi:app --port 5001 --reload
```

---

## 📚 Access Points

| What | URL |
|------|-----|
| **API Docs (Swagger)** | http://localhost:5001/docs |
| **Alternative Docs** | http://localhost:5001/redoc |
| **Health Check** | http://localhost:5001/health |
| **Service Info** | http://localhost:5001/ |

---

## 🎯 Next Steps

1. ✅ Service running? Go to http://localhost:5001/docs
2. ✅ Try the **GET /health** endpoint (click "Try it out")
3. ✅ Upload PDFs using **POST /analyze/batch** endpoint
4. ✅ Get session results via **GET /analysis/{session_id}**

---

**That's it! You're ready to go!** 🚀
.\venv\Scripts\activate
