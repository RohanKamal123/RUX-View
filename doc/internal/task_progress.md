# Vertex AI Migration — Task Progress

- [x] Analyze codebase and create migration plan
- [x] Update `requirements.txt` — replace google-generativeai with google-cloud-aiplatform
- [x] Rewrite `backend/ai/ai_client.py` — migrate from google-generativeai SDK to vertexai SDK
- [x] Update `backend/config.py` — add Vertex AI project/region config, mark gemini_api_key as deprecated
- [x] Update `backend/ai/CONTEXT.md` — reflect new SDK stack
- [x] Update `.env.example` — document Vertex AI setup
- [x] Update `infrastructure/cloud_run_config.yaml` — add GOOGLE_CLOUD_PROJECT/REGION env vars
- [x] Update `backend/tests/unit/test_ai_client.py` — update mocks for Vertex AI SDK
- [x] Verify all changes are consistent
