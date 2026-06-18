# Vision OS — End-to-End Testing Guide

> **Your Stack:** Gemini 2.0 Flash (vision + text + audio) | Telegram | MEGA.nz | IP Webcam  
> **Not Used:** Whisper, Groq, SMS, Payments, PostgreSQL (MEGA-only mode)

---

## 1. Prerequisites

### 1.1 Environment Variables (`.env`)

Ensure your `.env` has **all** of these:

```env
# ── MEGA.nz Storage ──────────────────
MEGA_EMAIL=run.rohan778@gmail.com
MEGA_PASSWORD=Rohan123#
MEGA_API_KEY=kvpeJS3gv8dJHjj9_zdENA

# ── AI (Gemini 2.0 Flash) ────────────
GEMINI_API_KEY=AIzaSyCXkT9wzRli2CUlTDyFRyD3dDXh8j8_5pI

# ── Telegram ──────────────────────────
TELEGRAM_BOT_TOKEN=8754384260:AAEBUkRLWQsA1EQ1C_SjzV3ienyjMw0Uvt0
TELEGRAM_CHAT_ID=<YOUR_CHAT_ID>       # ← YOU MUST ADD THIS

# ── App Mode ──────────────────────────
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

**To get your Telegram Chat ID:**
1. Open Telegram, search for `@userinfobot`
2. Start the bot → it replies with your chat ID (e.g., `123456789`)
3. Copy that number into `TELEGRAM_CHAT_ID` in `.env`

### 1.2 IP Webcam Setup (Your Phone)

1. Install **IP Webcam** app from Play Store on your Android phone
2. Open the app → tap **Start Server**
3. Note the URL shown (e.g., `http://192.168.1.101:8080`)
4. Verify it works: open `http://192.168.1.101:8080/video` in browser

---

## 2. Starting the Backend

```bash
# From project root (c:\Users\HP Zbook\Documents\RUX View)
uvicorn backend.dashboard.server:app --reload --host 0.0.0.0 --port 8000
```

**Verify it's running:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "storage": {
    "layer1_mega": "ok",
    "layer2_postgres": "unavailable"
  }
}
```

> `layer2_postgres: "unavailable"` is **normal** — you're running MEGA-only mode.

---

## 3. End-to-End Test Checklist

### Phase A: Backend API Tests (no camera needed)

#### A1. Health Check
```bash
curl http://localhost:8000/health
```
- [ ] Returns `200 OK`
- [ ] `status` is `"ok"`
- [ ] `layer1_mega` is `"ok"`

#### A2. Auth (Dev Mode — no Firebase needed)
```bash
curl -H "Authorization: Bearer test-token-123" http://localhost:8000/api/cameras/
```
- [ ] Returns `200` with camera list (empty is fine)
- [ ] No `401` error

#### A3. Create a Camera
```bash
curl -X POST http://localhost:8000/api/cameras/ \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "test-cam-001",
    "camera_name": "Front Gate Test",
    "rtsp_url": "http://192.168.1.101:8080/video",
    "mode": "indoor",
    "location": "Test Location"
  }'
```
- [ ] Returns `201 Created`
- [ ] Response includes `camera_id`

#### A4. List Cameras
```bash
curl -H "Authorization: Bearer test-token-123" http://localhost:8000/api/cameras/
```
- [ ] Returns the camera you just created

#### A5. Send a Test Frame Trigger
```bash
# First, capture a test image and base64 encode it
python -c "
import base64
with open('test_gemini_frames/frame_01_195255.jpg', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
print(b64[:50] + '...')
"

# Then send it
curl -X POST http://localhost:8000/api/triggers/frame \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "test-cam-001",
    "image_base64": "<paste_base64_here>",
    "timestamp": "2026-05-30T01:00:00Z",
    "confidence": 0.95
  }'
```
- [ ] Returns `200` with `event_id`
- [ ] Event is stored in MEGA.nz

#### A6. Get Recent Triggers
```bash
curl -H "Authorization: Bearer test-token-123" http://localhost:8000/api/triggers/recent
```
- [ ] Returns the event you just created

#### A7. Test NL Query
```bash
curl -X POST http://localhost:8000/api/queries/natural \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{"query": "motion", "camera_id": "test-cam-001"}'
```
- [ ] Returns matching events

#### A8. Test Query History
```bash
curl -H "Authorization: Bearer test-token-123" http://localhost:8000/api/queries/history
```
- [ ] Returns your query history

---

### Phase B: Gemini AI Tests

#### B1. Test Frame Analysis (Vision)
```bash
python -c "
import asyncio
from backend.ai.ai_client import analyse_frame

async def test():
    with open('test_gemini_frames/frame_01_195255.jpg', 'rb') as f:
        result = await analyse_frame(f.read())
    print('Persons:', result.get('person_count'))
    print('Alerts:', result.get('scene_alerts'))
    print('Full:', result)

asyncio.run(test())
"
```
- [ ] Returns person count
- [ ] No errors
- [ ] Response is valid JSON

#### B2. Test Detailed Frame Analysis
```bash
python -c "
import asyncio
from backend.ai.ai_client import analyse_frame_detailed

async def test():
    with open('test_gemini_frames/frame_01_195255.jpg', 'rb') as f:
        result = await analyse_frame_detailed(f.read())
    print('Scene:', result.get('scene'))
    print('Anomalies:', result.get('anomalies'))

asyncio.run(test())
"
```
- [ ] Returns detailed scene description
- [ ] No errors

#### B3. Test Incident Decision
```bash
python -c "
import asyncio
from backend.ai.ai_client import make_incident_decision

async def test():
    timeline = [{'time': '01:00:00', 'action': 'person detected near gate'}]
    context = {
        'camera_name': 'Front Gate',
        'camera_mode': 'indoor',
        'timestamp': '2026-05-30T01:00:00Z',
        'location_type': 'residential',
        'is_business_hours': False,
        'duration': 30,
        'reid_result': 'unknown',
        'is_known': False,
        'label': 'unknown',
        'audio_context': 'none',
        'history': []
    }
    result = await make_incident_decision(timeline, context)
    print('Threat Level:', result.get('threat_level'))
    print('Action:', result.get('action'))
    print('Message:', result.get('alert_message'))

asyncio.run(test())
"
```
- [ ] Returns threat level
- [ ] Returns action (LOG_ONLY / TELEGRAM_TEXT / TELEGRAM_PHOTO / EMERGENCY)

#### B4. Test Gemini Audio Analysis (Sound)
```bash
python -c "
import asyncio
from backend.ai.ai_client import _get_model

async def test():
    model = _get_model()
    # Test with a text prompt about sound analysis
    response = await model.generate_content_async(
        'Analyze this sound description: loud banging noise at front door. '
        'Return JSON: {\"sound_type\": \"...\", \"threat_level\": \"...\", \"description\": \"...\"}'
    )
    print(response.text)

asyncio.run(test())
"
```
- [ ] Gemini responds with sound analysis JSON

---

### Phase C: Telegram Alert Tests

#### C1. Test Telegram Text Alert
```bash
python -c "
import asyncio
from backend.alerts.telegram_client import TelegramClient
from backend.config import settings

async def test():
    bot = TelegramClient(settings.telegram_bot_token)
    success = await bot.send_text(
        settings.telegram_chat_id,
        'VisionOS TEST - This is a test alert from your local backend'
    )
    print('Sent:', success)
    await bot.close()

asyncio.run(test())
"
```
- [ ] You receive the message on Telegram
- [ ] Returns `True`

#### C2. Test Telegram Photo Alert
```bash
python -c "
import asyncio
from backend.alerts.telegram_client import TelegramClient
from backend.config import settings

async def test():
    bot = TelegramClient(settings.telegram_bot_token)
    with open('test_gemini_frames/frame_01_195255.jpg', 'rb') as f:
        jpeg = f.read()
    success = await bot.send_photo(
        settings.telegram_chat_id,
        jpeg,
        'VisionOS TEST - Test photo alert with caption'
    )
    print('Sent:', success)
    await bot.close()

asyncio.run(test())
"
```
- [ ] You receive the photo on Telegram
- [ ] Caption is visible

#### C3. Test Alert Router (Full Pipeline)
```bash
python -c "
import asyncio
from backend.alerts.telegram_client import TelegramClient
from backend.alerts.alert_router import AlertRouter
from backend.config import settings

async def test():
    bot = TelegramClient(settings.telegram_bot_token)
    router = AlertRouter(bot, None, None)  # No voice/SMS for now
    
    incident = {
        'threat_level': 'MEDIUM',
        'alert_message': 'Person detected at front gate at night',
        'camera_name': 'Front Gate Test',
        'timestamp': '2026-05-30T01:00:00Z',
        'jpeg_bytes': None
    }
    user = {
        'telegram_chat_id': settings.telegram_chat_id
    }
    
    action = await router.route_alert(incident, user, 'business')
    print('Channel:', action.channel)
    print('Message:', action.message)
    await bot.close()

asyncio.run(test())
"
```
- [ ] You receive the MEDIUM alert on Telegram
- [ ] Channel is `telegram_text`

---

### Phase D: Client Agent (VisionOS-Connect.exe) Tests

#### D1. Prepare Config for Your IP Webcam

Create `%APPDATA%\VisionOS\config.json`:

```json
{
  "api_key": "test-token-123",
  "camera_id": "test-cam-001",
  "camera_name": "Front Gate Test",
  "rtsp_url": "http://192.168.1.101:8080/video",
  "mode": "indoor",
  "backend_url": "http://localhost:8000",
  "audio_enabled": false,
  "auto_start": true,
  "motion_threshold": 0.02,
  "motion_min_area": 5000
}
```

> **Replace `192.168.1.101`** with your phone's actual IP from the IP Webcam app.

#### D2. Run the EXE

```bash
dist\VisionOS-Connect\VisionOS-Connect.exe
```

**What to observe:**
- [ ] System tray icon appears
- [ ] Console shows: `Connecting to camera...`
- [ ] Console shows: `Camera connected successfully`
- [ ] Console shows: `WebSocket connected`
- [ ] Console shows: `Processing started`

#### D3. Trigger Motion Detection

1. Walk in front of your phone camera
2. Observe the console:
   - [ ] `Motion detected` messages appear
   - [ ] `Sending frame trigger...` appears
   - [ ] `Frame trigger sent successfully` appears

#### D4. Verify on Backend

```bash
curl -H "Authorization: Bearer test-token-123" http://localhost:8000/api/triggers/recent
```
- [ ] New events appear from your camera

#### D5. Verify Telegram Alert

- [ ] You receive a Telegram alert about the motion detection

---

### Phase E: Full Pipeline Test (End-to-End)

This tests the complete flow: **Camera → Client Agent → Backend → Gemini → Telegram**

1. **Start backend** (if not already running):
   ```bash
   uvicorn backend.dashboard.server:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Start the EXE**:
   ```bash
   dist\VisionOS-Connect\VisionOS-Connect.exe
   ```

3. **Trigger motion** by walking in front of your phone camera

4. **Expected flow**:
   ```
   Phone Camera → RTSP stream → VisionOS-Connect.exe
     → MotionDetector detects motion
     → Frame captured → base64 encoded
     → POST /api/triggers/frame → Backend
     → Backend stores in MEGA.nz
     → Gemini analyses frame (vision)
     → Incident decision made
     → Alert routed via Telegram
     → You receive alert on phone 📱
   ```

5. **Verify each step**:
   - [ ] EXE console shows motion detection
   - [ ] EXE console shows trigger sent
   - [ ] Backend console shows trigger received
   - [ ] Backend console shows Gemini analysis
   - [ ] Backend console shows alert routed
   - [ ] Telegram notification received

---

## 4. Troubleshooting

### "MEGA.nz not initialized"
- Check `MEGA_EMAIL` and `MEGA_PASSWORD` in `.env`
- Ensure MEGA account is active

### "Camera connection failed"
- Verify IP webcam is running on your phone
- Test URL in browser: `http://192.168.1.101:8080/video`
- Both devices must be on the **same WiFi network**

### "No Telegram alert received"
- Verify `TELEGRAM_CHAT_ID` is correct
- Test with the direct Telegram test (Phase C1)
- Check backend logs for alert routing errors

### "Gemini analysis failed"
- Verify `GEMINI_API_KEY` is valid
- Check Gemini API quota (free tier: 60 requests/minute)
- Test with the direct Gemini test (Phase B1)

### "EXE crashes on startup"
- Check `%APPDATA%\VisionOS\crash.log`
- Ensure `config.json` has valid values
- Run from command prompt to see error output

---

## 5. Quick Smoke Test (All-in-One)

Run this to verify the entire backend is working:

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Create camera
curl -X POST http://localhost:8000/api/cameras/ \
  -H "Authorization: Bearer test" \
  -H "Content-Type: application/json" \
  -d '{"camera_id":"smoke-test","camera_name":"Smoke Test","rtsp_url":"http://test:8080/video","mode":"indoor"}'

# 3. Send trigger
curl -X POST http://localhost:8000/api/triggers/frame \
  -H "Authorization: Bearer test" \
  -H "Content-Type: application/json" \
  -d '{"camera_id":"smoke-test","image_base64":"dGVzdA==","timestamp":"2026-05-30T01:00:00Z","confidence":0.9}'

# 4. Get recent triggers
curl -H "Authorization: Bearer test" http://localhost:8000/api/triggers/recent

# 5. NL query
curl -X POST http://localhost:8000/api/queries/natural \
  -H "Authorization: Bearer test" \
  -H "Content-Type: application/json" \
  -d '{"query":"motion"}'
```

---

## 6. Pre-Shipment Checklist

Before shipping to beta testers:

- [ ] All 139 unit tests pass (`python -m pytest connect/tests/ -v`)
- [ ] Backend starts without errors (`uvicorn backend.dashboard.server:app`)
- [ ] Health check returns `200 OK`
- [ ] MEGA.nz storage initializes
- [ ] Gemini API key is valid
- [ ] Telegram bot sends messages
- [ ] EXE builds cleanly (`.\build_client.bat`)
- [ ] EXE starts and connects to IP webcam
- [ ] Motion triggers flow through to Telegram
- [ ] `.env` has `TELEGRAM_CHAT_ID` set
- [ ] `ENVIRONMENT=development` (for testing without Firebase)
