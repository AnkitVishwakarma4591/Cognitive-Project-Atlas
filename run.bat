@echo off
echo ========================================================
echo   Starting Project Atlas: Report Copilot Server
echo ========================================================

call .\venv\Scripts\activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
pause
