@echo off
cd src
python -m uvicorn server:app --host 0.0.0.0 --port 8000
pause
