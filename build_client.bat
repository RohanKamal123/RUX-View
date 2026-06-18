@echo off
REM ──────────────────────────────────────────────────────────────
REM Vision OS — Connect Edge Agent Build Script (Windows)
REM
REM RUN THIS FROM THE PROJECT ROOT (where connect/main.py lives)
REM
REM Produces: dist/VisionOS-Connect/
REM ──────────────────────────────────────────────────────────────

echo ========================================
echo  Vision OS — Building Connect Edge Agent
echo ========================================

REM Step 1: Install PyInstaller if not present
pip install pyinstaller 2>nul || (
    echo [ERROR] pip not found. Make sure Python is installed.
    exit /b 1
)

REM Step 2: Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Step 3: Run PyInstaller
echo [INFO] Running PyInstaller...
pyinstaller ^
    --clean ^
    --onedir ^
    --name "VisionOS-Connect" ^
    --hidden-import "pyaudio" ^
    --hidden-import "cv2" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "numpy" ^
    --hidden-import "requests" ^
    --hidden-import "httpx" ^
    --hidden-import "httpcore" ^
    --hidden-import "h11" ^
    --hidden-import "certifi" ^
    --hidden-import "idna" ^
    --hidden-import "sniffio" ^
    --hidden-import "websockets" ^
    --hidden-import "mega" ^
    --hidden-import "sqlite3" ^
    --hidden-import "pystray" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "connect.camera.rtsp_reader" ^
    --hidden-import "connect.camera.frame_selector" ^
    --hidden-import "connect.camera.motion_detector" ^
    --hidden-import "connect.audio.audio_capture" ^
    --hidden-import "connect.transport.trigger_sender" ^
    --hidden-import "connect.transport.websocket_client" ^
    --hidden-import "connect.buffer.local_queue" ^
    --hidden-import "connect.config" ^
    --hidden-import "connect.camera.connection_manager" ^
    --hidden-import "connect.camera.onvif_discovery" ^
    --collect-all "cv2" ^
    --collect-all "numpy" ^
    --collect-all "PIL" ^
    --collect-all "pystray" ^
    --collect-all "httpx" ^
    --exclude-module "setuptools" ^
    --exclude-module "packaging.licenses" ^
    --exclude-module "pkg_resources" ^
    --exclude-module "tensorflow" ^
    --exclude-module "tensorflow_hub" ^
    --noconfirm ^
    connect/main.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build failed with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo ========================================
echo  BUILD COMPLETE!
echo ========================================
echo.
echo Output: dist/VisionOS-Connect/
echo.
echo To distribute:
echo   1. Zip the dist/VisionOS-Connect/ folder
echo   2. Upload to your distribution channel
echo   3. Beta testers extract and run VisionOS-Connect.exe
echo.
echo NOTE: The .exe reads config from:
echo   %%APPDATA%%\VisionOS\config.json
echo.
echo If the .exe crashes, check:
echo   %%APPDATA%%\VisionOS\crash.log
echo.
pause
