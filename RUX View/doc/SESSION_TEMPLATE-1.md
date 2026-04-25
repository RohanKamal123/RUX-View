# SESSION_TEMPLATE.md
# Fill this in before every coding session.
# Takes 3 minutes. Prevents 3 hours of confusion.

---

# Session Start Checklist
[ ] Which sprint am I on?
[ ] Which single file am I building?
[ ] Is CONTEXT.md written for this module?
[ ] Have I opened ONLY this module's folder in Claude Code?
[ ] Do I have test fixtures ready?
[ ] Am I using the correct stack? Quick reference:
      AI client  → backend/ai/ai_client.py (Gemini 2.0 Flash, single file)
      Re-ID      → boxmot + pgvector (NOT torchreid/OSNet)
      Scheduler  → APScheduler AsyncIOScheduler (NOT schedule library)
      TTS        → Kokoro-82M (NOT gTTS/pyttsx3)
      Windows    → Nuitka (NOT PyInstaller)
      Embeddings → pgvector vector(512) column in Postgres

---

# My Prompt Today

Module:
File:
Function I need:
Test that proves it works:
Do NOT touch:
