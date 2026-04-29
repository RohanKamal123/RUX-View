@echo off
echo Starting CCTV Guard...

:: Detection (all cameras via threads)
start "CCTV Detection" python main.py

:: Wait a moment before starting server
timeout /t 3 /nobreak >nul

:: Web dashboard
start "CCTV Server" python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

:: ngrok tunnel
start "CCTV Tunnel" ngrok http 8000

echo.
echo All services started.
echo Dashboard: http://localhost:8000
echo Check ngrok window for public URL.
pause