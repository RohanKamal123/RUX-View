# ARCHITECTURE.md
# Vision OS — Complete Technical Specification
# Version 1.0 | Locked for V1 Build

---

## 1. PRODUCT OVERVIEW

### What It Is
Vision OS is an AI-powered CCTV intelligence SaaS platform for the Bangladesh market.
It connects to existing IP cameras and adds an intelligence layer — real-time incident
detection, audio transcription, cross-camera person tracking, and natural language
querying over security events.

### What It Is Not
- Not a recording product (customers keep their own DVR)
- Not a camera hardware product
- Not a replacement for Hikvision/Dahua
- Not a cloud storage product

### One Line Pitch
"Plug into any camera. Get AI-powered alerts, audio intelligence,
and natural language search over your security — starting at 299 BDT/month."

### Target Market
- Primary: Homeowners and residences in Bangladesh
- Secondary: Shop owners, godown operators, small offices
- Geography: Bangladesh only (V1)
- Camera range: 1–5 cameras per user (V1)

---

## 2. THREE-TIER PRICING MODEL

### FREE
```
Price:          0 BDT (1 month full trial, then restricted)
Cameras:        1–2
Event history:  7 days
Camera modes:   Indoor only
Alerts:         Telegram (20/day cap)
Daily digest:   Telegram simple summary ✅
Analytics:      None
Whisper:        None
NL Queries:     None
Re-ID:          None
Cross-camera:   None
Emergency:      None
SMS fallback:   None
After trial:    7 day grace → data deleted
                Warned on day 1, 5, 7 via Telegram
```

### HOUSEHOLD — 299 BDT/camera/month
```
Price:          299 BDT per camera per month
Cameras:        1–5
Event history:  30 days
Camera modes:   Indoor, Outdoor/Crowd, Parking, Mixed ✅
Alerts:         Telegram unlimited
Daily digest:   Telegram detailed ✅
Weekly digest:  ✅
Whisper:        ✅ Bangla transcription
Re-ID:          ✅ familiar face labelling
Cross-camera:   ✅ within same location
Ghost detect:   ✅
Person profiles:✅
Emergency:      ✅ Telegram voice note
SMS fallback:   ✅ SSL Wireless (HIGH only, outage only)
NL Queries:     ✅
Gemini chatbot: ✅
Target users:   Homeowners, residences, apartments, compounds
```

### BUSINESS — 499 BDT/camera/month
```
Price:          499 BDT per camera per month
Cameras:        1–5
Event history:  90 days
Camera modes:   ALL including Shop/Analytics ✅
Alerts:         Telegram unlimited
Daily digest:   Telegram detailed + shop analytics ✅
Weekly digest:  ✅ + weekly business report
Whisper:        ✅ Bangla transcription
Re-ID:          ✅ staff + customer separation
Cross-camera:   ✅ within same location
Ghost detect:   ✅
Person profiles:✅
Emergency:      ✅ Telegram voice note
SMS fallback:   ✅ SSL Wireless (HIGH only, outage only)
NL Queries:     ✅
Gemini chatbot: ✅
Shop analytics: ✅ customer counter, gender/age,
                   peak hours, dwell time,
                   staff vs customer separation
Godown mode:    ✅ strict after hours, cargo detection
Target users:   Shops, showrooms, restaurants,
                godowns, offices, warehouses
```

---

## 3. SYSTEM ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│              CUSTOMER PREMISES (per location)               │
│                                                             │
│  IP Camera(s) ──RTSP──► Vision OS Connect (Windows/Android) │
│                          ├── Motion detection (pixel diff)  │
│                          ├── Sound detection (YAMNet)       │
│                          ├── Best frame capture             │
│                          ├── Local SQLite buffer (48hr)     │
│                          └── Outbound WebSocket only        │
└──────────────────────────────┬──────────────────────────────┘
                               │ JPEG triggers + audio chunks
                               │ (outbound only, no NAT issues)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                YOUR BACKEND (Google Cloud Run)              │
│                                                             │
│  FastAPI ──► Trigger receiver                              │
│              ├── Incident state machine (per camera)       │
│              ├── Cross-camera correlation engine           │
│              ├── Re-ID engine (BoxMOT + pgvector)          │
│              ├── AI client (Gemini 2.0 Flash — unified)    │
│              ├── Whisper client (OpenAI API)               │
│              ├── Query engine (NL → SQL → Gemini 2.0)      │
│              ├── Analytics engine (shop/business mode)     │
│              ├── Alert router (Telegram + SMS)             │
│              └── Dashboard server                          │
└──────┬────────────────────┬───────────────────────────────┘
       │                    │
       ▼                    ▼
┌─────────────┐    ┌────────────────────────┐
│ GEMINI API  │    │   CLOUD SQL (Postgres) │
│             │    │   + pgvector           │
│ Gemini 2.0  │    │                        │
│ Flash       │    │ events                 │
│ → vision    │    │ persons                │
│ → decisions │    │   + embedding vector   │
│ → chatbot   │    │ scene_states           │
│ → queries   │    │ analytics              │
│ → digests   │    │ cameras                │
│             │    │ users                  │
│             │    │ locations              │
└─────────────┘    └────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACES                          │
│                                                             │
│  Web Dashboard (FastAPI + Jinja2)                          │
│  Android Viewer App (thin client, Kotlin)                  │
│  Telegram Bot (alerts + digests + emergency)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. VISION OS CONNECT (CLIENT AGENT)

### Purpose
Lightweight background agent installed once per physical location.
Solves the NAT problem — all connections are outbound only.
Customer never touches router settings.

### Platform Priority
1. Windows (.exe via Nuitka) — primary, most BD homes have a PC
2. Android (.apk) — secondary, for phone-as-relay use cases

### What It Does
```
1. Connect to IP camera on local network via RTSP
2. Run motion detection locally (pixel diff — free, no API)
3. Run sound detection locally (YAMNet — free, on device)
4. On trigger only:
   → Select best frame (8 frame lookahead, highest contour score)
   → Capture audio chunk (8 seconds around trigger)
   → POST JPEG + audio to backend via outbound HTTPS
5. Maintain persistent outbound WebSocket (heartbeat 30s)
6. Buffer locally if internet drops (SQLite, 48hr / 500 events max)
7. Flush buffer on reconnect (oldest first, backdated)
8. Send SMS via SSL Wireless for HIGH alerts during outage
```

### What It Does NOT Do
```
→ No continuous video streaming to server
→ No inbound connections (no port forwarding needed)
→ No Gemma/AI on client (all AI is server-side)
→ No video storage
```

### Install Flow for Customer
```
1. Sign up at dashboard
2. Dashboard generates QR code / API key
3. Download Vision OS Connect
4. Open app → scan QR (auto-configures server connection)
5. Enter camera RTSP URL + credentials
   Example: rtsp://admin:password@192.168.1.64:554/stream
6. Name the camera: "Front Gate"
7. Name the location: "Home - Mirpur"
8. Select camera mode: Indoor / Outdoor / Parking / Mixed / Shop
9. Draw ignore zones on preview (optional)
10. Click Connect → status turns green
11. First trigger fires within minutes
```

### Multi-Location Support
```
User has 3 locations (home, shop, godown):
→ Install Connect separately at each location
→ Use same API key at all locations
→ Each location operates independently
→ Dashboard shows unified view across all locations
→ Cross-camera Re-ID works within location only
   (same person cannot be in godown AND shop simultaneously)
```

### Offline Behaviour
```
STATE 1: Full internet ✅
→ Normal operation

STATE 2: Internet down, local network up
→ Detection continues locally
→ Triggers queue in local SQLite
→ HIGH threat → SSL Wireless SMS sent (~0.30 BDT)
→ Internet returns → flush queue → backdated alerts
→ Telegram digest: "While offline, 3 events occurred"

STATE 3: Full outage (power/router dead)
→ Nothing works → accept for V1
→ Camera itself may have local SD storage (not our concern)
```

---

## 5. CAMERA MODES

### MODE 1: INDOOR
```
Use case: Living room, bedroom, hallway, office interior
Individual tracking: ✅ full
Re-ID: ✅
Loitering detection: ✅
Ghost detection: ✅
Whisper: ✅
Familiar faces: ✅
Night mode: ✅ automatic

Motion parameters:
  Min contour area:   1500px²
  Sample rate:        every 3rd frame
  Pixel diff skip:    < 400
  Pixel diff check:   400–2500
  Pixel diff Gemma:   > 2500
  Pixel diff urgent:  > 7000
```

### MODE 2: OUTDOOR / CROWD
```
Use case: Street-facing cameras, public road view
Individual tracking: ❌ (public space, meaningless)
Crowd anomaly: ✅ (MOG2 background subtraction)
Re-ID: ❌
Loitering: ❌ (public space)
Alerts on: crowd scatter, density anomaly,
           abandoned object, person falling,
           wrong-way vehicle

MOG2 baseline: learns "normal" over first 24 hours
Anomaly = significant deviation from baseline
Gemma fires: only on HIGH anomaly (1–2x/hour max)

Motion parameters:
  Min contour area:   3500px²
  Sample rate:        every 5th frame
  Pixel diff skip:    < 800
  Pixel diff check:   800–4000
  Pixel diff Gemma:   > 4000
  Pixel diff urgent:  > 10000
```

### MODE 3: MIXED (partial outdoor view)
```
Use case: Camera sees both inside property and public road
Setup: user draws two zones on camera preview
  PROPERTY ZONE → full indoor intelligence
  PUBLIC ZONE → anomaly only, no individual tracking

Key trigger: person crossing PUBLIC → PROPERTY zone
  Must be in property zone > 2 seconds (filter passersby)
  Gemma fires immediately on crossing
  Full incident tracking begins

Person stays in public zone:
  → ignore individually
  → crowd anomaly still monitored
  → "incident near property" if anomaly detected
```

### MODE 4: PARKING
```
Use case: Parking lots, driveways, vehicle storage areas
Primary subjects: vehicles + person-vehicle interactions
Individual tracking: ✅
Re-ID: ✅

Key triggers:
  → Vehicle enters parking zone
  → Person approaches parked vehicle
  → Person-vehicle interaction (opening/crouching/loading)
  → Unattended vehicle (after hours)
  → Headlight detection at night (bright pixel burst)

Gemma prompt focus:
  → Vehicle type, color, visible plate region
  → Person-vehicle interaction description
  → Number of people around vehicle
  → Forced entry indicators

Person loitering near vehicle:
  Own vehicle:          ignore < 5 min
  Others vehicle day:   LOW 45s / MEDIUM 90s / HIGH 150s
  After hours any:      LOW 15s / MEDIUM 30s / HIGH 60s

Vehicle long stay:
  Business hours:       no alert
  After hours > 30min:  LOW (possible abandoned)
  After hours > 2hrs:   MEDIUM

Night triggers:
  Headlight flash:      wake from idle immediately
  Any vehicle entry:    Gemma immediately
  Engine running > 10min stationary: flag (surveillance?)

Cross-camera with gate:
  Person leaves parking → check gate camera
  Not seen at gate → "person in parking, no gate entry"
  → MEDIUM flag (possible wall entry)

Motion parameters:
              Day       Night
  Skip:       < 600     < 400
  Check:      600–3500  400–2500
  Gemma:      > 3500    > 2500
  Urgent:     > 9000    > 6000
```

### MODE 5: SHOP / ANALYTICS (Business tier only)
```
Use case: Shop floors, showrooms, restaurant entrances,
          godown entry points

BUSINESS HOURS BEHAVIOUR:
  Entrance zone → count every entry
  Gemma on entry → age group + gender estimation
  Staff filter → active (don't count staff)
  Loitering on shop floor → DISABLED
  Loitering in back room/storage → ENABLED
  After hours → switch to security mode automatically

ANALYTICS COLLECTED:
  → Customer entry count (total per day)
  → Gender breakdown (male/female/unknown %)
  → Age group breakdown (teens/20s/30s/40s/50s+)
  → Dwell time per customer (> 30s to count)
  → Peak hour heatmap (15 min buckets)
  → Staff vs customer separation

STAFF IDENTIFICATION:
  → Re-ID match to labelled staff profiles
  → OR entering via staff entrance zone
  → OR arriving before shop opens (owner configures time)

GODOWN SPECIFICS:
  → All zones treated as restricted
  → After hours = maximum security mode
  → Object carrying detection (Gemma: what are they carrying?)
  → Unauthorized access = immediate HIGH alert

ANALYTICS REPORT TRIGGERS:
  Live counter:   updates every 15 minutes on dashboard
  Daily digest:   at shop closing time (user configures)
                  OR midnight if not configured
  Weekly report:  Monday 8am
```

---

## 6. INTELLIGENCE PIPELINE

### 6.1 Incident State Machine

Every camera has its own independent state machine running on the backend.

```
┌─────────────┐
│    IDLE     │◄────────────────────────────────┐
│             │                                 │
│ Gemma: OFF  │                                 │
│ Cost: $0    │                                 │
│             │                                 │
│ pixel diff  │                                 │
│ check only  │                                 │
└──────┬──────┘                                 │
       │                                        │
       │ motion passes ALL filters              │
       │ + cooldown elapsed                     │
       ▼                                        │
┌─────────────┐                                 │
│  TRACKING   │                                 │
│             │                                 │
│ Gemma: ON   │                                 │
│ burst every │                                 │
│ 2.5s when   │                                 │
│ behaviour   │                                 │
│ changes     │                                 │
└──────┬──────┘                                 │
       │                                        │
       │ no motion 3–6s (mode dependent)        │
       │ OR max incident cap hit                │
       ▼                                        │
┌─────────────┐                                 │
│    CLOSE    │                                 │
│  INCIDENT   │─────────────────────────────────┘
│             │
│ send full   │
│ timeline    │
│ to Gemini   │
│             │
│ route alert │
│ save to DB  │
└─────────────┘
```

### 6.2 Vision Client Call Gate (When to Call, When to Skip)

```
ALWAYS CALL VISION CLIENT (Gemini 2.0 Flash):
→ First frame of any incident (establish who/what)
→ Pixel diff crosses URGENT threshold
→ Loitering escalation timer fires
→ Person crossing from public → property zone
→ After hours ANY motion (night mode)
→ Re-ID uncertainty (similarity 0.5–0.72)
→ Audio trigger + no current visual incident open
→ Vehicle entry in parking mode
→ Person approaches vehicle in parking mode

SKIP VISION CLIENT:
→ Re-ID confidence > 0.85 AND person is labelled known
→ Business hours, staff Re-ID match confirmed
→ Pixel diff below CHECK threshold
→ Within burst cooldown AND pixel diff unchanged
→ Same action as 10s ago (heartbeat skip, no new info)
→ Public zone only (outdoor mode)
```

### 6.3 Pixel Diff Thresholds by Mode

```
              Indoor    Outdoor   Parking   Night
              ────────────────────────────────────
Skip:         < 400     < 800     < 600     < 300
Check:        400–2500  800–4000  600–3500  300–2000
Gemma:        > 2500    > 4000    > 3500    > 2000
Urgent:       > 7000    > 10000   > 9000    > 5000
```

### 6.4 Incident Timing Parameters

```
              Indoor  Outdoor  Parking  Shop    Night
              ──────────────────────────────────────
Cooldown (s): 15      30       20       10      8
Burst (s):    2.5     2.5      2.5      2.5     1.5
Urgent (s):   0.8     0.8      0.8      0.8     0.8
No motion(s): 3       6        4        3       4
Max cap (s):  60      60       120      300*    60
              *shop floor: unlimited during business hours
```

### 6.5 Loitering Escalation Timers

```
Location          LOW      MEDIUM   HIGH     NOTES
────────────────────────────────────────────────────────
Front gate:       45s      120s     240s
Parking (others): 45s      90s      150s
Parking afterhrs: 15s      30s      60s
Godown:           30s      60s      120s
After hours any:  20s      45s      90s
Shop floor:       DISABLED during business hours
Shop back room:   30s      60s      120s
Indoor general:   60s      180s     300s
```

### 6.6 Repeat Sighting Escalation

```
Same person (Re-ID match), same day, same location:
  1st sighting:  LOG only
  2nd sighting:  LOW alert
  3rd sighting:  MEDIUM + "seen X times today"
  4th sighting:  HIGH + emergency Telegram voice note
  5th+ sighting: HIGH every time

Reset conditions:
  → 6 hours no sighting → reset counter
  → EXCEPTION: night hours (10pm–6am) NEVER reset
  → EXCEPTION: after hours at business location NEVER reset
```

### 6.7 Ghost Detection

```
Trigger: person seen entering location,
         not seen on any camera for defined window

  10 minutes unaccounted: MEDIUM alert
  "Person entered property, not seen leaving"

  30 minutes unaccounted: HIGH alert
  "Unaccounted person on property for 30 minutes"

  Cancelled if: person seen on any camera
                OR user dismisses manually

Extra useful: parking cross-check
  Person in parking → not seen at gate
  → "Person in parking area, no gate entry detected"
  → MEDIUM (possible wall/fence entry)
```

### 6.8 Night Mode

```
Active hours: 10pm – 6am (user configurable per camera)
Auto-detect:  if Gemma detects dark/IR conditions
              → override schedule, enable night mode

Changes in night mode:
  Sensitivity:        × 1.5 (all thresholds lowered)
  Cooldown:           halved
  Burst interval:     1.5s (from 2.5s)
  Any motion:         always Gemma call (no skip)
  Staff filter:       DISABLED (no staff at night)
  Unknown person:     MEDIUM minimum (never just LOG)
  Emergency:          ENABLED (disabled during day)
  Repeat sighting:    counter never resets
  Loitering timers:   all halved
```

---

## 7. RE-ID ENGINE

### Approach: Hybrid (BoxMOT + Appearance Description)

```
Step 1: Gemini 2.0 Flash extracts person crop bbox from frame
        "bbox_normalized": [0.2, 0.1, 0.45, 0.9]

Step 2: Crop person from frame using bbox

Step 3: BoxMOT (FastReID backend) extracts 512-dim embedding
        Library: boxmot (pip install boxmot)
        Backend: FastReID MobileNet (~4MB, MIT license)
        Tracker: BoT-SORT integrated with YOLO11 detections
        Time: ~0.8s on CPU (faster than previous OSNet 1.2s)

Step 4: Cosine similarity via pgvector in Postgres
        SELECT person_uid FROM persons
        ORDER BY embedding <-> %s LIMIT 5
        > 0.85  → confident match → return existing ID
        0.5–0.72 → uncertain → go to Step 5
        < 0.5   → new person → mint new ID
        (Python-side numpy loops eliminated — see D022)

Step 5 (uncertain zone only):
        Compare Gemini appearance description strings
        using SequenceMatcher similarity
        Combined score determines final ID
        If still uncertain → ai_client.reid_tiebreaker()
        sends both descriptions to Gemini 2.0 Flash

Person signature format:
  "male 20s red-shirt black-jeans white-sneakers backpack"

New person ID format: PERSON_001 through PERSON_999
```

### Person Identity Object (stored in Postgres)

```json
{
  "person_id": "PERSON_007",
  "first_seen": "2024-01-15T09:14:01",
  "first_camera": "front_gate",
  "first_location": "home_mirpur",
  "sighting_count": 7,
  "cameras_seen": ["front_gate", "parking", "side_gate"],
  "threat_flags": 1,
  "is_staff": false,
  "label": "Unknown",
  "user_label": null,
  "appearance_history": [
    {
      "timestamp": "2024-01-15T09:14:01",
      "camera_id": "front_gate",
      "clothing_description": "red shirt black jeans",
      "embedding_id": "emb_20240115_001",
      "thumbnail_key": "thumbs/person007_001.jpg"
    }
  ]
}
```

### Familiar Face Labelling

```
Owner can label any Re-ID profile:
  "Postman", "Gardener", "Staff 1", "Family"

Effect on alerts:
  Known person + label → different alert format
  "Known visitor [Postman] at front gate"
  vs
  "Unknown person at front gate"

Staff label (Business tier):
  → Excluded from customer analytics counts
  → After hours → still alerts (shouldn't be there)
  → Separate staff attendance log generated

Owner can label via:
  → Dashboard person profile page
  → Tap on any event thumbnail → "Label this person"
```

### Cross-Camera Re-ID

```
Scope: within same physical location only
       (godown and shop are separate locations)

Match window by location type:
  Indoor building:  5 minutes
  Home compound:    10 minutes
  Large property:   20 minutes

Spatial logic (camera topology):
  User defines neighbours during setup:
  front_gate → driveway → parking → back_door

  If PERSON_007 at front_gate at 14:32:
  → Check driveway within 2 min
  → Check parking within 5 min
  → If at back_door at 14:33 (1 min gap):
    → IMPOSSIBLE to walk that fast
    → Flag: "Possible different person OR fence jump"

Cross-camera timeline shown on person profile page:
  14:32 front_gate → 14:35 driveway → 14:38 parking
```

---

## 8. AUDIO INTELLIGENCE

### Layer 1: YAMNet (On Client — Free)

```
Runs on customer's PC/phone, no API cost
Model size: 3.7MB
Classes relevant to security: 521 total

Thresholds to trigger Whisper:
  Glass breaking:     > 0.75
  Gunshot/firearm:    > 0.70 → also triggers emergency
  Shouting/screaming: > 0.72
  Dog barking:        > 0.85 → LOW alert only, no Whisper
  Alarm/siren:        > 0.80
  Speech (generic):   > 0.80 (after hours only)
  Crowd noise:        > 0.85 (outdoor mode only)

YAMNet fires → sends audio chunk (8s) + classification
to backend with confidence score
```

### Layer 2: Whisper (OpenAI API — Small Model)

```
Triggered when: YAMNet confidence above threshold
                AND one of:
                → After hours confirmed
                → YAMNet class is HIGH threat sound
                → Visual incident already open (±15s window)

Model: whisper-1 (small, best Bangla accuracy)
Cost: $0.006/minute → 8s clip = $0.0008 per trigger
Expected: 10 triggers/day → $0.008/day per camera

Output: raw Bangla transcript + timestamps
        "কেউ চিৎকার করছে, চোর চোর"

Sent to: Gemini for interpretation
```

### Layer 3: Gemini 2.0 Flash Interpretation

```
Receives: Whisper transcript + YAMNet classification
          + visual incident context if open

Outputs:
  threat_interpretation: "Shouting 'thief thief' near gate"
  threat_level: HIGH
  action: TELEGRAM_PHOTO + emergency

Dashboard shows:
  Raw transcript (Bangla)
  Gemini interpretation (English summary)
  Visual correlation if camera also triggered
  "Sound detected, no visual — possible blind spot"

Storage: 1–3 days (transcripts are sensitive)
```

### Audio-Visual Correlation

```
Audio trigger fires:
→ Check if visual incident open on same camera: ±10s
→ Check neighbour cameras for visual: ±15s
→ Found visual → merge into same incident
  "Person seen at gate + shouting detected"
→ No visual → audio-only incident
  "Shouting detected, no visual confirmation"
  → This itself is suspicious (blind spot activity)
```

---

## 9. AI STACK

### Gemini 2.0 Flash — Unified Client (backend/ai/ai_client.py)

All AI functions — vision analysis, incident decisions, NL queries, digests, and
Re-ID tiebreaking — go through a single client using `google-generativeai` SDK.
No Vertex AI SDK. No separate gemma_client.py / gemini_client.py.

**Live Vision Prompt (fast — used during incidents):**
```
Analyse this CCTV frame quickly. Return JSON only.
No explanation. No markdown.

{
  "persons": [{
    "gender": "male/female/unknown",
    "age_estimate": 28,
    "clothing": "red shirt, black jeans",
    "hand_objects": ["phone"],
    "carried_items": ["backpack"],
    "action": "walking/running/standing/crouching/climbing",
    "anomaly_signals": [],
    "bbox_normalized": [0.2, 0.1, 0.45, 0.9]
  }],
  "person_count": 1,
  "scene_alerts": [],
  "vehicles": [],
  "gates_visible": {}
}
```

**Query Prompt (detailed — used for on-demand NL queries):**
```
Analyse this CCTV frame in extreme detail.
This data answers user queries like
"who wore red?" or "what was in their hand?"
Be obsessively descriptive. Return JSON only.

{
  "persons": [{
    "gender": "male/female/unknown",
    "age_estimate": 28,
    "clothing": {
      "top": "exact color and garment type",
      "bottom": "exact color and type",
      "shoes": "description or unknown",
      "accessories": ["cap", "watch", "glasses"]
    },
    "hand_objects": ["mobile phone", "keys"],
    "carried_items": ["black backpack"],
    "action": "detailed action description",
    "body_language": "relaxed/nervous/aggressive/hurried",
    "face_direction": "looking at camera/away/down",
    "position": "description relative to doors/gates/objects",
    "bbox_normalized": [0.2, 0.1, 0.45, 0.9]
  }],
  "scene": {
    "gates": {"gate_1": "open/closed/unknown"},
    "doors": {"front_door": "open/closed/unknown"},
    "vehicles": ["white sedan parked left"],
    "unattended_objects": ["black bag near gate"],
    "lighting": "daylight/night/artificial/IR",
    "weather_hint": "sunny/overcast/rainy/dark"
  },
  "anomalies": []
}
```

**Analytics Prompt (shop mode — used on customer entry):**
```
Analyse the person entering this shop.
Return JSON only.

{
  "gender": "male/female/unknown",
  "age_group": "teen/20s/30s/40s/50s+/unknown",
  "carried_items": ["shopping bag", "phone"],
  "group_size": 1,
  "confidence": 0.87
}
```

**Incident Decision Prompt:**
```
You are a CCTV security analyst for a property in Bangladesh.

Camera: {camera_name}
Mode: {camera_mode}
Time: {timestamp}
Location type: {location_type}
Business hours: {is_business_hours}

Incident timeline (vision observations):
{timeline}

Duration: {duration}s
Re-ID result: {reid_result}
Known person: {is_known} ({label})
Audio context: {audio_context}
Recent history (last 10 events this camera): {history}

Return JSON only:
{
  "threat_level": "LOW/MEDIUM/HIGH",
  "alert_message": "one sentence, plain text, no markdown",
  "action": "LOG_ONLY/TELEGRAM_TEXT/TELEGRAM_PHOTO/EMERGENCY",
  "reasoning": "brief explanation",
  "person_ids": ["PERSON_007"],
  "follow_up": "any recommended action for owner"
}
```

**Query Answer Prompt:**
```
You are analysing CCTV event data to answer a user question.
Answer directly. Reference person IDs and timestamps.
If uncertain, say so. Plain text, not JSON.

User question: {question}
Camera(s): {cameras}
Time range: {range}
User tier: {tier}

Matching events from database:
{events_json}

Vision analysis of matching frames:
{vision_analyses}
```

**Scene State Prompt:**
```
Current observed state across all cameras.
Answer the user's question directly.
If a gate/door hasn't been seen recently, say when
it was last observed and its state at that time.

World state: {world_state_json}
Last observation age per camera: {recency}
User question: {question}
```

**Daily Digest Prompt:**
```
Generate a daily security summary for a {location_type}
owner in Bangladesh. Plain text. Friendly but informative.
Maximum 200 words for Telegram.

Date: {date}
Events: {events_summary}
Person stats: {person_stats}
Audio events: {audio_summary}
Anomalies: {anomalies}
Shop analytics (if applicable): {shop_data}
Tier: {tier}
```

**Re-ID Tiebreaker Prompt (uncertainty zone 0.5–0.72):**
```
Two CCTV person sightings. Determine if same person.
Return JSON only.

Sighting A: {appearance_description_a}
Sighting B: {appearance_description_b}
Time gap: {minutes} minutes
Cameras: {camera_a} → {camera_b}

{
  "same_person": true/false,
  "confidence": 0.0–1.0,
  "reasoning": "brief explanation"
}
```

---

## 10. DATABASE SCHEMA

### events
```sql
CREATE TABLE events (
  id                  SERIAL PRIMARY KEY,
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  camera_id           VARCHAR(100) NOT NULL,
  incident_id         VARCHAR(100) NOT NULL,
  timestamp_start     TIMESTAMPTZ NOT NULL,
  timestamp_end       TIMESTAMPTZ,
  duration_sec        FLOAT,
  threat_level        VARCHAR(10),        -- LOW/MEDIUM/HIGH
  alert_sent          BOOLEAN DEFAULT FALSE,
  alert_type          VARCHAR(30),        -- LOG/TEXT/PHOTO/EMERGENCY
  camera_mode         VARCHAR(20),        -- indoor/outdoor/parking/shop/mixed
  is_business_hours   BOOLEAN,
  gemma_raw_json      JSONB,
  gemini_decision     JSONB,
  timeline_json       JSONB,             -- all burst observations
  thumbnail_url       TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_user_time ON events(user_id, timestamp_start DESC);
CREATE INDEX idx_events_camera ON events(camera_id, timestamp_start DESC);
CREATE INDEX idx_events_threat ON events(user_id, threat_level, timestamp_start DESC);
```

### persons
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE persons (
  id                  SERIAL PRIMARY KEY,
  person_uid          VARCHAR(20) NOT NULL,  -- PERSON_007
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  first_seen          TIMESTAMPTZ,
  last_seen           TIMESTAMPTZ,
  sighting_count      INTEGER DEFAULT 0,
  threat_flags        INTEGER DEFAULT 0,
  is_staff            BOOLEAN DEFAULT FALSE,
  user_label          VARCHAR(100),          -- "Postman", "Gardener"
  appearance_history  JSONB,
  embedding           vector(512),           -- pgvector: BoxMOT/FastReID embedding
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(person_uid, user_id)
);

-- IVFFlat index for fast approximate cosine similarity search
CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops);
```

### person_sightings
```sql
CREATE TABLE person_sightings (
  id                  SERIAL PRIMARY KEY,
  person_uid          VARCHAR(20) NOT NULL,
  user_id             UUID NOT NULL,
  event_id            INTEGER REFERENCES events(id),
  camera_id           VARCHAR(100),
  timestamp           TIMESTAMPTZ,
  clothing_top        TEXT,
  clothing_bottom     TEXT,
  clothing_colors     TEXT,
  accessories         TEXT,
  hand_objects        TEXT,
  action              TEXT,
  anomaly_signals     TEXT,
  embedding           vector(512),           -- pgvector column
  thumbnail_url       TEXT
);

CREATE INDEX idx_sightings_person ON person_sightings(person_uid, user_id, timestamp DESC);
```

### scene_states
```sql
CREATE TABLE scene_states (
  id                  SERIAL PRIMARY KEY,
  camera_id           VARCHAR(100) NOT NULL,
  user_id             UUID NOT NULL,
  timestamp           TIMESTAMPTZ NOT NULL,
  gates_json          JSONB,    -- {"gate_1": "closed", "gate_2": "open"}
  doors_json          JSONB,
  vehicles_json       JSONB,
  lighting            VARCHAR(30),
  person_count        INTEGER,
  raw_scene_json      JSONB
);

CREATE INDEX idx_scene_camera_time ON scene_states(camera_id, timestamp DESC);
```

### audio_events
```sql
CREATE TABLE audio_events (
  id                  SERIAL PRIMARY KEY,
  event_id            INTEGER REFERENCES events(id),
  camera_id           VARCHAR(100),
  user_id             UUID NOT NULL,
  timestamp           TIMESTAMPTZ,
  yamnet_class        VARCHAR(100),
  yamnet_confidence   FLOAT,
  whisper_transcript  TEXT,
  gemini_interpretation TEXT,
  threat_level        VARCHAR(10),
  has_visual_match    BOOLEAN DEFAULT FALSE,
  expires_at          TIMESTAMPTZ           -- 1–3 days retention
);
```

### shop_analytics
```sql
CREATE TABLE shop_analytics (
  id                  SERIAL PRIMARY KEY,
  camera_id           VARCHAR(100),
  user_id             UUID NOT NULL,
  date                DATE NOT NULL,
  hour                INTEGER,              -- 0–23
  customer_count      INTEGER DEFAULT 0,
  male_count          INTEGER DEFAULT 0,
  female_count        INTEGER DEFAULT 0,
  unknown_gender      INTEGER DEFAULT 0,
  age_teens           INTEGER DEFAULT 0,
  age_20s             INTEGER DEFAULT 0,
  age_30s             INTEGER DEFAULT 0,
  age_40s             INTEGER DEFAULT 0,
  age_50plus          INTEGER DEFAULT 0,
  avg_dwell_seconds   FLOAT,
  UNIQUE(camera_id, date, hour)
);
```

### cameras
```sql
CREATE TABLE cameras (
  id                  VARCHAR(100) PRIMARY KEY,
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  name                VARCHAR(200),
  mode                VARCHAR(20),          -- indoor/outdoor/parking/mixed/shop
  enabled             BOOLEAN DEFAULT TRUE,
  tier_required       VARCHAR(20),          -- free/household/business
  gemma_cooldown_sec  INTEGER DEFAULT 15,
  ignore_zones_json   JSONB,
  shop_hours_open     TIME,
  shop_hours_close    TIME,
  night_hours_start   TIME DEFAULT '22:00',
  night_hours_end     TIME DEFAULT '06:00',
  loiter_config_json  JSONB,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### locations
```sql
CREATE TABLE locations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL,
  name                VARCHAR(200),         -- "Home - Mirpur"
  type                VARCHAR(30),          -- home/shop/godown/office
  camera_topology     JSONB,               -- neighbour relationships
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### users
```sql
CREATE TABLE users (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firebase_uid        VARCHAR(200) UNIQUE,
  email               VARCHAR(200),
  phone               VARCHAR(20),          -- bKash number
  telegram_chat_id    VARCHAR(50),
  telegram_bot_token  VARCHAR(200),
  tier                VARCHAR(20) DEFAULT 'free',
  trial_started_at    TIMESTAMPTZ,
  trial_ends_at       TIMESTAMPTZ,
  subscription_active BOOLEAN DEFAULT FALSE,
  bkash_subscriber_id VARCHAR(200),
  secondary_contact   VARCHAR(50),          -- for emergency escalation
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 11. ALERT SYSTEM

### Alert Routing by Threat Level

```
LOW:      → Dashboard only, no Telegram
MEDIUM:   → Telegram text message
HIGH:     → Telegram photo + caption
EMERGENCY:→ Telegram urgent message + voice note
            Retry every 90s, max 3 attempts
            If no response → send to secondary_contact
            If still no response → log as unacknowledged

During internet outage (HIGH only):
          → SSL Wireless SMS (~0.30 BDT)
          "VisionOS ALERT: High threat at [camera].
           Check Telegram when online."
```

### Telegram Message Formats (plain text, no markdown)

```
MEDIUM:
VisionOS MEDIUM - Front Gate - 14:32:01
Male approx 30yo loitering 2 minutes
Camera: Home Front Gate

HIGH (caption on photo):
VisionOS HIGH ALERT - Parking - 02:17:44
Unknown person near vehicle
Loitering 3 minutes after hours
Person: PERSON_007 (seen 2x today)
Action: crouching near white sedan

EMERGENCY:
VisionOS EMERGENCY - Godown - 03:44:12
Unknown person climbing fence
4th sighting today
Check your property immediately
Reply SAFE to acknowledge

DAILY DIGEST (free tier):
VisionOS Daily - 15 Jan
Front Gate: 8 events, 0 HIGH
Parking: 2 events, 0 HIGH
Visitors: 6 (4 familiar, 2 unknown)
Audio: 0 alerts
All clear today.

DAILY DIGEST (household/business):
VisionOS Daily Summary - 15 Jan
[Location: Home Mirpur]

Security: 11 events total
  HIGH: 0  MEDIUM: 1  LOW: 10
Visitors: 9 (7 familiar, 2 unknown)
PERSON_007 seen 3x - flagged
Audio: 1 event (dog barking 22:14)
Gate status: All closed as of 23:58

[View full report on dashboard]
```

### Emergency Voice Note
```
Telegram voice note (Kokoro-82M TTS — local, not gTTS):
"Vision OS emergency alert.
 High threat detected at [camera name].
 [Time]. Check your dashboard immediately."

Generated on backend server via Kokoro-82M (Apache 2.0)
Converted WAV → OGG Opus via ffmpeg for Telegram
Sent as .ogg file to Telegram chat
Plays automatically on notification
Natural-sounding voice (not robotic)
```

---

## 12. NATURAL LANGUAGE QUERY ENGINE

### Flow
```
User types query in dashboard
→ Query parser (Gemini 2.0 Flash) extracts intent + filters
→ SQL pre-filter on structured fields (fast, free)
→ Identify matching event IDs + timestamps
→ For each match: retrieve stored vision analysis JSON
  (if not stored: re-analyse thumbnail via Gemini 2.0 Flash)
→ Gemini 2.0 Flash synthesises final answer
→ Dashboard shows: text answer + matching thumbnails
```

### Query Types

```
APPEARANCE:
"who wore red shirts today?"
"find the person in the blue cap"
"show everyone who carried a bag"
→ SQL: WHERE clothing_top ILIKE '%red%'
        AND timestamp > today

OBJECT IN HAND:
"what was person 7 holding in parking?"
"who had a package after 6pm?"
→ SQL: WHERE person_uid = 'PERSON_007'
        AND camera_id ILIKE '%parking%'
→ Gemma detail prompt on matching frames

SCENE STATE:
"are all gates locked right now?"
"was the back door open today?"
→ Latest scene_states per camera
→ Gemini reads world state → answers directly

BEHAVIOUR:
"did anyone run today?"
"show HIGH threat events this week"
→ SQL: WHERE action ILIKE '%run%'
        AND timestamp > last_7_days

CROSS-CAMERA:
"track person 7 across all cameras today"
→ SQL: WHERE person_uid = 'PERSON_007'
        ORDER BY timestamp ASC
→ Returns full timeline across cameras

TIMELINE:
"what happened while I was away 2pm to 6pm?"
→ SQL: WHERE timestamp BETWEEN 14:00 AND 18:00
→ Gemini writes narrative summary
```

---

## 13. FILE STRUCTURE

```
vision-os/
│
├── connect/                         CLIENT AGENT
│   ├── main.py                      entry point
│   ├── camera/
│   │   ├── rtsp_reader.py           RTSP stream connection
│   │   ├── frame_selector.py        best frame from N frames
│   │   └── motion_detector.py       pixel diff + zone masking
│   ├── audio/
│   │   ├── yamnet_detector.py       YAMNet sound classification
│   │   └── audio_capture.py        audio chunk extraction
│   ├── transport/
│   │   ├── websocket_client.py      persistent outbound connection
│   │   ├── trigger_sender.py        JPEG + audio POST to backend
│   │   └── sms_sender.py           SSL Wireless fallback
│   ├── buffer/
│   │   └── local_queue.py          SQLite offline buffer
│   ├── ui/
│   │   └── tray_app.py             Windows system tray
│   ├── config.py                   location + camera config
│   └── tests/
│       ├── test_motion_detector.py
│       ├── test_frame_selector.py
│       └── test_local_queue.py
│
├── backend/                         SERVER
│   ├── api/
│   │   ├── triggers.py              receive triggers from Connect
│   │   ├── dashboard.py             dashboard routes
│   │   ├── queries.py               NL query endpoints
│   │   ├── cameras.py               camera management
│   │   ├── users.py                 user management
│   │   └── billing.py               bKash endpoints
│   │
│   ├── core/
│   │   ├── pipeline.py              main orchestrator per camera
│   │   ├── incident_tracker.py      IDLE/TRACKING/CLOSE state machine
│   │   ├── cross_camera.py          multi-camera correlation engine
│   │   ├── ghost_detector.py        unaccounted person logic
│   │   └── repeat_sighting.py       frequency escalation logic
│   │
│   ├── ai/
│   │   ├── ai_client.py             Gemini 2.0 Flash unified wrapper
│   │   │                            (vision + decisions + queries + digests)
│   │   ├── whisper_client.py        OpenAI Whisper wrapper
│   │   ├── reid_engine.py           BoxMOT hybrid Re-ID + pgvector lookup
│   │   └── query_engine.py          NL query processing
│   │
│   ├── modes/
│   │   ├── indoor_mode.py           indoor intelligence logic
│   │   ├── outdoor_mode.py          MOG2 crowd anomaly
│   │   ├── parking_mode.py          vehicle + person logic
│   │   ├── mixed_mode.py            zone-based split logic
│   │   └── shop_mode.py             analytics + business logic
│   │
│   ├── analytics/
│   │   ├── shop_analytics.py        customer counting + demographics
│   │   ├── digest_generator.py      daily + weekly digest
│   │   └── report_builder.py        business reports
│   │
│   ├── storage/
│   │   ├── database.py              Postgres schema + queries
│   │   └── cleanup.py              retention + deletion jobs
│   │
│   ├── alerts/
│   │   ├── telegram_client.py       Telegram Bot API
│   │   ├── alert_router.py          route by threat + tier
│   │   ├── voice_note.py            TTS emergency voice
│   │   └── sms_client.py           SSL Wireless integration
│   │
│   ├── billing/
│   │   └── bkash_client.py          bKash payment API
│   │
│   ├── dashboard/
│   │   ├── server.py                FastAPI app
│   │   ├── auth.py                  Firebase Auth middleware
│   │   ├── templates/
│   │   │   ├── base.html
│   │   │   ├── index.html           main event feed
│   │   │   ├── camera.html          per-camera view
│   │   │   ├── person.html          person profile page
│   │   │   ├── query.html           NL query interface
│   │   │   ├── analytics.html       shop analytics
│   │   │   └── settings.html        camera + account settings
│   │   └── static/
│   │       ├── app.js
│   │       └── style.css
│   │
│   └── tests/
│       ├── unit/
│       │   ├── test_incident_tracker.py
│       │   ├── test_cross_camera.py
│       │   ├── test_reid_engine.py
│       │   ├── test_ghost_detector.py
│       │   ├── test_repeat_sighting.py
│       │   ├── test_parking_mode.py
│       │   ├── test_shop_mode.py
│       │   └── test_alert_router.py
│       ├── integration/
│       │   ├── test_pipeline_flow.py
│       │   ├── test_audio_visual_correlation.py
│       │   └── test_query_engine.py
│       ├── e2e/
│       │   └── test_full_incident.py
│       └── fixtures/
│           ├── test_frames/         saved JPEGs
│           ├── test_audio/          saved WAV clips
│           └── mock_responses/      saved Gemma/Gemini JSON
│
├── android/                         VIEWER APP (thin client)
│   └── app/src/main/
│       ├── ui/                      dashboard viewer screens
│       ├── notifications/           FCM push handler
│       └── data/                    API client
│
├── docs/                            MkDocs documentation
│   ├── architecture/
│   ├── modules/
│   ├── api/
│   └── decisions/
│
├── .github/
│   └── workflows/
│       ├── test.yml                 pytest on every push
│       ├── deploy.yml               deploy to Cloud Run on main
│       └── docs.yml                 rebuild MkDocs on push
│
├── ARCHITECTURE.md                  ← this document
├── DECISIONS.md                     why every choice was made
├── CHANGELOG.md                     version history
├── BUILD_PLAN.md                    sprint by sprint plan
└── requirements.txt
```

---

## 14. DEPENDENCIES

```
BACKEND (Python)
────────────────────────────────
fastapi
uvicorn[standard]
gunicorn                   async workers (UvicornWorker)
google-generativeai        Gemini 2.0 Flash (replaces google-cloud-aiplatform)
openai                     Whisper API
boxmot                     Re-ID: BoT-SORT + FastReID (replaces torchreid)
pgvector                   vector similarity in Postgres (psycopg2 extension)
opencv-python              MOG2 + frame processing
firebase-admin             Firebase Auth verification
psycopg2-binary            Postgres
sqlalchemy                 ORM
python-dotenv              env vars
httpx                      async HTTP (replaces requests — needed for asyncio)
apscheduler                async cron scheduler (replaces schedule)
kokoro                     Kokoro-82M TTS for voice notes (replaces gTTS)
Pillow                     image processing

CLIENT AGENT (Python → .exe)
────────────────────────────────
opencv-python              motion detection
tensorflow                 YAMNet audio
pyaudio                    audio capture
websockets                 persistent connection
httpx                      trigger POST (async)
sqlite3                    local buffer (stdlib)
pystray                    Windows system tray
nuitka                     compile to native .exe (replaces PyInstaller)

ANDROID VIEWER (Kotlin)
────────────────────────────────
Retrofit + OkHttp          API client
Firebase Auth              login
Firebase Cloud Messaging   push notifications
Glide                      image loading

INFRASTRUCTURE
────────────────────────────────
Google Cloud Run            backend hosting
Google Cloud SQL            Postgres + pgvector extension
Gemini API (google-generativeai) vision + reasoning (replaces Vertex AI)
Firebase Auth               user authentication
Firebase Cloud Messaging    push notifications
OpenAI API                  Whisper transcription
SSL Wireless BD             SMS fallback
bKash Payment Gateway       billing
Telegram Bot API            alerts (free)
```

---

## 15. SOLO BUILD RULES

```
1. MAX 200 LINES PER FILE
   If bigger → split into two files
   Smaller files = better Claude context

2. ONE MODULE AT A TIME
   Finish → test → document → commit
   Never work on two modules simultaneously

3. EVERY FUNCTION HAS A TEST
   Written immediately after the function
   No exceptions, no "I'll add tests later"

4. CONTEXT.md PER MODULE
   Each folder has CONTEXT.md
   Contains: purpose, interface, dependencies
   Paste at start of every Claude session for that module

5. DECISIONS.md UPDATED DAILY
   Every architectural choice explained
   Prevents re-arguing settled decisions

6. COMMIT AFTER EVERY WORKING FEATURE
   Message format: "feat: [module] what it does"
   Green tests = safe to commit

7. GITHUB ACTIONS FROM DAY ONE
   Tests run on every push automatically
   Nothing merges to main with failing tests

8. CLAUDE CONTEXT STRUCTURE
   Each Claude session starts with:
   → CONTEXT.md for this module
   → Relevant section of ARCHITECTURE.md
   → Test fixtures available
   → Exact function signature needed
   → Ask for: code + tests + docstring in one response
```

---

## 16. COST ESTIMATES

### Per Camera Per Day

```
Gemini 2.0 Flash — vision + decisions (unified)
  15 incidents × 5 frames avg
  + 15 decision calls (~800 tokens each)
  Gemini 2.0 Flash pricing: ~$0.00010/image, ~$0.00004/decision
  = $0.009/day  (lower than previous split Gemma+Gemini estimate)

Whisper audio (Household/Business)
  10 triggers × 8s = 80s audio
  $0.006/min = $0.008/day

Cloud SQL Postgres
  Shared, amortised per camera
  = $0.002/day

Cloud Run backend
  Shared, amortised per camera
  = $0.005/day

Firebase
  Free tier covers V1 scale
  = $0.000/day
─────────────────────────────
HOUSEHOLD: ~$0.024/day = ~$0.72/month  (↓ from $0.81 — Gemini 2.0 Flash savings)
BUSINESS:  ~$0.034/day = ~$1.02/month  (↓ from $1.10)
FREE:      ~$0.006/day = ~$0.18/month  (↓ from $0.20)
```

### Revenue vs Cost at Scale

```
              Cost/cam/mo  Price/cam/mo  Margin
Free:         $0.18        $0            -$0.18
Household:    $0.72        $2.72         $2.00 (74%)
Business:     $1.02        $4.54         $3.52 (78%)

At 50 paying users, avg 2 cams:
  MRR: ~49,000 BDT ($450)
  Cost: ~11,500 BDT ($105)
  Profit: ~37,500 BDT ($345/month)
```

---

## 17. BUILD SEQUENCE

```
PHASE 1 — FOUNDATION (Week 1–2)
─────────────────────────────────────────────
[ ] Postgres schema + pgvector extension (database.py)
[ ] Firebase Auth middleware (auth.py)
[ ] Gemini 2.0 Flash unified client (ai_client.py)
[ ] Whisper client (whisper_client.py)
[ ] All API contracts stubbed (api/*.py)
[ ] CI pipeline (GitHub Actions pytest)
[ ] CONTEXT.md for every module
Output: skeleton runs, all tests written (failing OK)

PHASE 2 — CLIENT AGENT (Week 3–4)
─────────────────────────────────────────────
[ ] RTSP reader (rtsp_reader.py)
[ ] Motion detector (motion_detector.py)
[ ] Frame selector (frame_selector.py)
[ ] YAMNet audio detector (yamnet_detector.py)
[ ] Local SQLite buffer (local_queue.py)
[ ] WebSocket client + trigger sender
[ ] Windows system tray app
[ ] Package as .exe (Nuitka)
Output: Connect app working on real camera

PHASE 3 — CORE INTELLIGENCE (Week 5–6)
─────────────────────────────────────────────
[ ] Incident tracker state machine
[ ] Indoor mode
[ ] Outdoor/crowd mode (MOG2)
[ ] Parking mode
[ ] Mixed mode (zone-based)
[ ] BoxMOT Re-ID engine + pgvector similarity
[ ] Cross-camera correlation
[ ] Ghost detector
[ ] Repeat sighting escalation
[ ] Alert router + Telegram client
Output: Full pipeline end-to-end on real camera

PHASE 4 — AUDIO + BUSINESS (Week 7–8)
─────────────────────────────────────────────
[ ] Audio-visual correlation
[ ] Whisper integration
[ ] Shop/analytics mode
[ ] Shop analytics aggregation
[ ] Digest generator (APScheduler)
[ ] Night mode parameters
[ ] Emergency voice note (Kokoro-82M TTS)
[ ] SMS fallback (SSL Wireless)
Output: All modes working, alerts firing correctly

PHASE 5 — DASHBOARD + QUERIES (Week 9–10)
─────────────────────────────────────────────
[ ] Dashboard all pages
[ ] NL query engine
[ ] Person profile pages
[ ] Shop analytics dashboard
[ ] Firebase Auth login flow
[ ] bKash billing integration
[ ] 1 month trial logic
[ ] Data retention + cleanup jobs (APScheduler)
Output: Full user journey works end to end

PHASE 6 — STABILITY (Week 11–12)
─────────────────────────────────────────────
[ ] Edge case handling
[ ] Offline resilience testing
[ ] Multi-location testing (2+ locations)
[ ] Load testing (10 concurrent cameras)
[ ] Android viewer app
[ ] Beta onboarding (5–10 real users)
[ ] Fix real-world bugs
Output: Stable enough to charge money
```

---

*ARCHITECTURE.md — Vision OS V1*
*Status: UPDATED — stack revisions applied (D001/D007/D022–D026)*
*Last updated: Stack revision — Gemini 2.0 Flash unified, BoxMOT Re-ID, pgvector, Kokoro TTS, APScheduler, Nuitka*
