# CONTEXT.md — Alerts Module
# Module: backend/alerts/
# Sprint: 3.5
# Purpose: Alert routing + delivery channels

---

## What This Module Does

Four files handling all alert delivery:

1. **alert_router.py** — Route by threat level + tier
2. **telegram_client.py** — Telegram Bot API
3. **voice_note.py** — Kokoro-82M TTS for emergency voice notes
4. **sms_client.py** — SSL Wireless SMS fallback

---

## File: alert_router.py

### Routing Logic
```
LOW:      → Dashboard only, no Telegram
MEDIUM:   → Telegram text message
HIGH:     → Telegram photo + caption
EMERGENCY:→ Telegram urgent message + voice note
            Retry every 90s, max 3 attempts
            If no response → secondary contact
            If still no response → log as unacknowledged

During internet outage (HIGH only):
          → SSL Wireless SMS (~0.30 BDT)
```

### Functions
```python
async def route_alert(incident: dict, user: dict, tier: str) -> AlertAction
    # Returns: {channel, message, retry_count, acknowledged}
```

---

## File: telegram_client.py

### Functions
```python
async def send_text(chat_id: str, message: str) -> bool
    # Plain text, NO markdown (timestamp underscores)

async def send_photo(chat_id: str, jpeg_bytes: bytes, caption: str) -> bool

async def send_voice(chat_id: str, ogg_bytes: bytes, caption: str) -> bool
```

### Message Formats (plain text)
```
MEDIUM:
VisionOS MEDIUM - Front Gate - 14:32:01
Male approx 30yo loitering 2 minutes
Camera: Home Front Gate

HIGH:
VisionOS HIGH ALERT - Parking - 02:17:44
Unknown person near vehicle
Loitering 3 minutes after hours

EMERGENCY:
VisionOS EMERGENCY - Godown - 03:44:12
Unknown person climbing fence
4th sighting today
```

---

## File: voice_note.py

### Stack
```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code='a')  # American English for V1
```

### Functions
```python
async def generate_voice_note(camera_name: str, timestamp: str, threat_summary: str) -> bytes
    # Returns: OGG Opus bytes for Telegram
    # Text: "{camera_name}. {timestamp}. {threat_summary}."
    # Convert WAV → OGG via ffmpeg
```

### Key Decisions
- **D023** — Kokoro-82M (NOT gTTS/pyttsx3)
- Natural-sounding voice (not robotic)

---

## File: sms_client.py

### Functions
```python
async def send_sms(phone: str, message: str) -> bool
    # Via SSL Wireless API
    # ~0.30 BDT per SMS
```

## Dependencies
- httpx (async HTTP)
- kokoro (TTS)
- ffmpeg (WAV→OGG conversion)

## Called By
- backend/core/pipeline.py
- APScheduler (digest sending)
