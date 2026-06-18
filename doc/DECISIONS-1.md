# DECISIONS.md
# Vision OS — Architectural Decision Record
# Every major choice and why it was made

---

## D001 — Gemini 2.0 Flash (unified) instead of local Ollama or split Gemma/Gemini clients

**Decision:** Use a single Gemini 2.0 Flash client via Google AI SDK for ALL vision and reasoning tasks — replaces both the original Gemma 4 plan (D001) and the separate Gemini Flash client (D002)

**Why:**
- Original plan split work across two clients: Gemma 4 for vision analysis, Gemini Flash for reasoning/decisions
- Gemini 2.0 Flash handles both natively — multimodal vision + reasoning in one API call
- Eliminates Sprint 1.3 complexity: one client file instead of gemma_client.py + gemini_client.py
- Gemini 2.0 Flash is faster and cheaper than Gemma 4 on Vertex at equivalent quality
- Single client = single SDK, single auth, single billing line
- Pivot to cloud means customer needs ZERO powerful hardware
- Google ecosystem: Gemini + Firebase + Cloud Run = fully cohesive

**Tradeoff accepted:**
- API cost per call (~$0.00010/image at Gemini 2.0 Flash pricing — lower than original Gemma 4 estimate)
- Internet required for AI analysis
- Mitigated by: event-triggered only (not every frame)

**Migration from original plan:**
- Delete planned gemma_client.py — not needed
- Rename gemini_client.py → ai_client.py
- All Gemma prompt functions (analyse_frame, analyse_shop_entry) move into ai_client.py
- All Gemini prompt functions (make_incident_decision, answer_query, generate_digest) stay in same file

---

## D002 — SUPERSEDED by D001

**Decision:** Merged into D001. Gemini 2.0 Flash handles both vision analysis and reasoning.
Previously: separate Gemini Flash client for decisions/reasoning tasks.
No separate client needed — see D001.

---

## D003 — Groq for audio transcription

**Decision:** Groq for Bangla transcription


**Upgrade path:**

---

## D004 — YAMNet on client device, not server

**Decision:** YAMNet sound classifier runs on customer's PC/phone

**Why:**
- 3.7MB model, runs on any hardware
- Filters audio before sending to server (saves bandwidth + Whisper cost)
- Only HIGH confidence sound events trigger Whisper API
- 90% of ambient sound never leaves the device
- Free. No API cost.

---

## D005 — Trigger-only architecture (not continuous streaming)

**Decision:** Client sends JPEG + audio chunks on trigger, NOT continuous video stream

**Why:**
- Continuous 360p stream per camera = ~300kbps constant bandwidth
- 3 cameras = 900kbps customer upload (kills BD internet for other uses)
- At 100 users × 3 cameras = 270Mbps server ingress (expensive)
- Trigger-only: 50 triggers/day × 150KB = 7.5MB/day (negligible)
- Motion detection is FREE and runs locally — excellent filter
- 97% bandwidth reduction with zero loss of intelligence

---

## D006 — No video recording in V1

**Decision:** Do NOT record or store video footage

**Why:**
- Customers already have Hikvision/Dahua DVR doing this better
- 360p video is WORSE quality than their existing setup
- Storage cost: $1.80/camera/month (adds 54% to our cost)
- Battery drain on continuous upload
- Complex offline queue just for video
- Thumbnails + timestamps + rich text = sufficient
- "Open your DVR at 14:32:01" is acceptable for BD market
- Confirmed with potential customers: they already do this manually

**What we store instead:**
- 1 JPEG thumbnail per event (~50-100KB)
- Rich Gemma JSON (clothing, objects, actions)
- Timestamps with second precision
- Audio transcripts (1-3 days)

**Revisit for V2:** if users consistently request clip playback

---

## D007 — BoxMOT (BoT-SORT + FastReID backend) instead of OSNet/torchreid

**Decision:** Use `boxmot` library with BoT-SORT tracker + FastReID embedding backend, replacing OSNet via torchreid

**Why:**
- torchreid is poorly maintained: last meaningful update 2021, dependency conflicts with modern PyTorch, installation frequently breaks
- torchreid's 1.2s CPU latency per trigger compounds fast across 5 cameras
- `boxmot` is actively maintained (2024-2025), pip-installable, MIT license
- BoxMOT supports BoT-SORT (already in original architecture notes), OSNet, FastReID, and MobileNetV2 backends — one library covers all options
- FastReID backend is faster than OSNet at equivalent accuracy (~88-91%)
- BoT-SORT integrates directly with YOLO11 detections — no extra crop/embed pipeline needed
- Same hybrid approach preserved: embedding similarity + appearance string tiebreaker

**Accuracy targets (unchanged):**
- Pure string matching: ~65% (too low)
- BoxMOT hybrid: ~88-92% on clear crops, degrades gracefully to string match
- Uncertainty zone (0.5-0.72 cosine): Gemini 2.0 Flash tiebreaker call

**Installation:** `pip install boxmot` — no custom model download scripts needed

**Migration from original plan:**
- backend/ai/reid_engine.py: replace `torchreid` import with `boxmot`
- Embedding extraction API is near-identical, tests require minimal changes
- Model weight: ~4MB (FastReID MobileNet backend) — comparable to OSNet's 2.2MB

---

## D008 — Five camera modes instead of one

**Decision:** Indoor / Outdoor / Parking / Mixed / Shop as separate modes

**Why:**
- Single logic for all camera types = disaster
- BD outdoor camera sees 200+ motion events/hour (street traffic)
- Applying indoor loitering logic to public street = 1000 false alerts/day
- Shop floor loitering detection = every customer is "suspicious"
- Parking needs vehicle-aware logic (cars don't trigger person Re-ID)
- Mixed mode solves the "40% outdoor view" problem without cropping

**User sets mode once during setup. System handles the rest.**

---

## D009 — Vision OS Connect agent solves NAT problem

**Decision:** Lightweight client agent (Windows primary) with outbound-only connections

**Why:**
- Port forwarding: 80% of BD homeowners cannot do this
- Router admin pages often in Chinese, confusing
- Dynamic IP changes daily (need DDNS too)
- Security risk: exposed camera to internet
- Edge device (Raspberry Pi): upfront cost = customer friction
- Agent on existing Windows PC: zero hardware cost, 2 min install
- Outbound WebSocket always works through NAT (same as WhatsApp)
- Offline buffer: handles BD internet drops gracefully

---

## D010 — Telegram for ALL alerts including emergency

**Decision:** Telegram Bot for everything — alerts, digests, emergency voice notes

**Why:**
- Already in the stack (existing beta implementation)
- 99% of BD users have Telegram or can install it
- Telegram Bot API: completely free, unlimited messages
- Voice notes play immediately on notification (better than phone call)
- User sees thumbnail + hears alert simultaneously
- Unknown phone call = often ignored in BD
- Twilio/local VoIP: unnecessary cost and complexity
- WhatsApp Business API: charges per message

**SMS (SSL Wireless) only for:**
- Internet outage scenarios
- HIGH threat when user cannot receive Telegram
- ~0.30 BDT per SMS, negligible cost

---

## D011 — bKash for billing (not Stripe)

**Decision:** bKash personal account (upgrade to merchant when needed)

**Why:**
- Target market is Bangladesh — bKash is the dominant payment method
- ~80% of BD adults use bKash
- Stripe: requires international card, less common in BD
- bKash merchant API available when trade license ready
- Personal bKash usable for initial beta revenue collection
- Simplest path to first paying customer

---

## D012 — Firebase Auth, not custom auth

**Decision:** Firebase Authentication for user login

**Why:**
- Google Sign-in: users trust it
- Free tier covers thousands of users
- Already in Google ecosystem (Vertex, Cloud Run)
- Handles token management, session security, password reset
- Firebase Auth + Cloud Run = seamless integration
- Building custom auth = 2 weeks wasted for zero differentiator

---

## D013 — Cloud SQL Postgres, not Firestore

**Decision:** Cloud SQL Postgres for all data storage

**Why:**
- NL query engine needs complex SQL (JOIN, JSONB queries, full-text search)
- Firestore is NoSQL — terrible for "find all red shirts today" queries
- Postgres JSONB supports rich event data + structured queries
- Analytics aggregations need GROUP BY, window functions
- Postgres is the correct tool for this query pattern
- Cost comparable to Firestore at V1 scale

---

## D014 — Three pricing tiers (Free / Household / Business)

**Decision:** Free + 299 BDT Household + 499 BDT Business

**Why:**
- Validated with 10+ potential customers
- Free tier: acquisition and conversion tool
- Household (299 BDT): ~$2.72/camera — 70% margin at our cost
- Business (499 BDT): ~$4.54/camera — 76% margin
- Shop analytics exclusive to Business: clear upgrade incentive
- 1 month full trial: let product sell itself
- Per-camera pricing: scales naturally with customer's setup

**Free tier daily Telegram digest:**
- Keeps free users engaged
- "2 unknown visitors today" → they want to upgrade to see WHO
- Best organic conversion trigger
- Zero extra cost (one message/day)

---

## D015 — Repeat sighting escalation (1st LOG → 4th EMERGENCY)

**Decision:** Same person seen 4x same day = emergency escalation

**Why:**
- 1-2 sightings = could be delivery, neighbour, coincidence
- 3 sightings = emerging pattern, worth noting
- 4 sightings = deliberate surveillance behaviour
- Reset after 6 hours (legitimate repeat visitors exist)
- Night hours: never reset (no innocent reason to appear 4x at night)
- This logic catches real threats while minimising false positives

---

## D016 — Ghost detection (unaccounted person)

**Decision:** Person seen entering, not seen leaving = alert after 10/30 min

**Why:**
- Most sophisticated feature — no CCTV product does this affordably
- Requires cross-camera topology (user defines neighbour relationships)
- 10 min: could be using bathroom, taking time inside
- 30 min: genuinely concerning, HIGH alert
- False positive mitigation: user can dismiss manually
- Parking variant: person in parking + no gate entry = possible wall/fence access

---

## D017 — MOG2 background subtraction for outdoor mode

**Decision:** OpenCV MOG2 for outdoor/crowd anomaly, not person tracking

**Why:**
- Individual tracking on public BD street = meaningless and expensive
- MOG2 learns "normal" baseline over 24 hours
- Anomaly = statistical deviation from baseline
- Crowd scatter, density changes, abandoned objects detectable
- Near-zero cost (runs on client, no Gemma needed for most events)
- Gemma only fires on HIGH anomaly (1-2x/hour maximum)
- ByteTrack considered but deferred to V2

---

## D018 — Solo build with Claude as engineering team

**Decision:** Build solo with Claude instances per module, not hire team

**Why:**
- No budget for skilled engineers currently
- Average developers as co-founders = wrong move (founder's instinct)
- Claude context per module = focused, consistent output
- 200-line file limit = Claude handles each file completely in one context
- CONTEXT.md pattern = no re-explaining architecture each session
- Automated testing = Claude's QA team
- GitHub Actions CI = never ship broken code
- This approach viable for 1-5 camera V1 scope

**Module ownership:**
- Each folder has dedicated Claude context
- You (founder) = architect + product owner + final QA
- Never explain the same thing twice (DECISIONS.md carries context)

---

## D019 — 200 line maximum per file

**Decision:** Hard limit of 200 lines per source file

**Why:**
- Claude context window handles focused files better than large ones
- Forces single responsibility per module
- Easier to test (smaller surface area)
- Easier to debug (problem is isolated)
- If a file needs more than 200 lines → it has two responsibilities → split it

---

## D020 — Whisper transcript stored only 1-3 days

**Decision:** Audio transcripts deleted after 1-3 days

**Why:**
- Transcripts capture ambient conversation near cameras
- Privacy risk: someone's private conversation transcribed
- Bangladesh has no strong data protection law yet
- But moral obligation exists regardless of legal requirement
- 1-3 days enough for user to read and act on alert
- Long-term: only store Gemini interpretation, not raw transcript
- This becomes a trust/marketing advantage: "we don't keep your conversations"

---

## D021 — Per-camera pricing model

**Decision:** Price per camera, not per user or per location

**Why:**
- Aligns cost with actual server load (more cameras = more processing)
- Customer with 1 camera pays less than customer with 5 cameras
- Natural upgrade path: customer adds camera = revenue grows
- Industry standard for CCTV software (Verkada, Milestone do same)
- Simple to explain: "299 BDT per camera per month"
- bKash subscription amount adjusts when cameras added/removed

---

---

## D022 — pgvector extension in Cloud SQL Postgres for Re-ID embeddings

**Decision:** Store person embeddings directly in Cloud SQL Postgres using the `pgvector` extension, not a separate vector store

**Why:**
- Re-ID requires similarity search over 512-dim embeddings (cosine distance)
- Original plan implied storing embeddings as BLOBs and doing similarity in Python — slow and unscalable
- pgvector adds `vector` column type + `<->` operator for native cosine/L2 similarity search
- Available on Cloud SQL Postgres — no extra service, no extra cost, no extra auth
- `ORDER BY embedding <-> query_embedding LIMIT 5` — single SQL query covers Re-ID lookup
- Eliminates Python-side numpy similarity loops entirely
- Keeps all data in one place: events, persons, embeddings, transcripts — one DB, one backup policy

**Implementation:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE persons ADD COLUMN embedding vector(512);
CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops);
```

**Tradeoff accepted:**
- pgvector IVFFlat index needs ~100+ vectors to be useful; below that, exact scan is fine
- Acceptable: V1 scale is well below this threshold

---

## D023 — Kokoro-82M for emergency voice notes, not gTTS/pyttsx3

**Decision:** Use Kokoro-82M open-source TTS for generating voice note audio, replacing gTTS and pyttsx3

**Why:**
- gTTS: requires internet call to Google TTS API, robotic voice quality, adds latency to emergency path
- pyttsx3: offline but sounds like Windows XP, unpleasant on Telegram voice notes
- Kokoro-82M (Apache 2.0, 2025): runs on CPU, ~82M parameters, produces natural-sounding speech
- Emergency voice notes that sound robotic get ignored — natural voice = higher engagement
- Zero API cost, runs on backend server
- pip-installable: `pip install kokoro`
- ~300ms generation on CPU for a 5-second voice note — acceptable for emergency path

**Tradeoff accepted:**
- ~450MB model weight on server — acceptable for Cloud Run with persistent volume
- English-only for V1; Bangla TTS deferred to V2

---

## D024 — APScheduler instead of `schedule` library for digest jobs

**Decision:** Use APScheduler (AsyncIOScheduler) for all cron-style jobs (digest, cleanup, transcript expiry)

**Why:**
- `schedule` library is synchronous — blocks the FastAPI event loop
- APScheduler is async-native: `AsyncIOScheduler` integrates directly with FastAPI startup
- Supports cron expressions, interval triggers, one-shot jobs in one unified API
- Handles missed jobs on restart (with jobstore backed by Postgres)
- Actively maintained, production-grade

**Implementation:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(run_daily_digest, "cron", hour=22, minute=0)
scheduler.start()  # called in FastAPI lifespan
```

**Migration:** Replace all `schedule.every().day.at()` references in BUILD_PLAN sprints with APScheduler equivalents

---

## D025 — Nuitka instead of PyInstaller for Windows agent packaging

**Decision:** Use Nuitka to compile Vision OS Connect to a Windows .exe, replacing PyInstaller

**Why:**
- PyInstaller bundles Python interpreter + bytecode — Windows Defender regularly false-positives these as malware
- Non-technical BD homeowners will panic at "virus detected" popup and uninstall
- Nuitka compiles Python → C → native binary: smaller, faster startup, no interpreter bundle
- False-positive rate from antivirus tools is significantly lower for Nuitka binaries
- Comparable build complexity — `nuitka --onefile --windows-icon=icon.ico main.py`

**Tradeoff accepted:**
- Nuitka build takes 3-5 minutes vs PyInstaller's 30 seconds — only affects dev build loop, not users
- Some C compiler setup required (MinGW or MSVC) — one-time setup cost

---

## D026 — FastAPI worker model: Uvicorn + Gunicorn with async pipeline

**Decision:** Run FastAPI on Cloud Run with `gunicorn -k uvicorn.workers.UvicornWorker --workers 2` and use `asyncio.gather()` for parallel per-camera AI calls

**Why:**
- Default single-worker Uvicorn blocks on concurrent camera triggers
- At 5 cameras firing simultaneously: sequential processing = 5× latency spike
- `asyncio.gather()` over Gemini 2.0 Flash calls = parallel non-blocking I/O
- 2 workers on Cloud Run 2-vCPU instance = optimal for I/O-bound workload
- Prevents one slow Gemini response from blocking another camera's pipeline

**Implementation note:**
- CameraPipeline.process_trigger() must be `async def`
- All Gemini/Whisper calls must use `await` (httpx async client, not requests)
- background_tasks.add_task() in FastAPI trigger endpoint keeps HTTP response fast

---

*DECISIONS.md — Vision OS V1*
*Update this file every time a new architectural decision is made*
*Format: D[number] — Title / Decision / Why / Tradeoff accepted*
