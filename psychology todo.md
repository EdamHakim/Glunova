# Psychology Module TODO (Based on `Psychology Architecture.md`)

This checklist maps the architecture spec to current implementation status so the team can execute remaining work in order.

## Already Done

### Core API and Flow Skeleton
- [x] Added psychology API router in FastAPI with main endpoints:
  - `POST /psychology/session/start`
  - `POST /psychology/message`
  - `POST /psychology/emotion/frame`
  - `GET /psychology/session/{id}`
  - `GET /psychology/trends/{patient_id}`
  - `GET /psychology/crisis/events`
  - `POST /psychology/session/end`
- [x] `POST /psychology/crisis/ack` — acknowledge a crisis row (doctor/caregiver; caregiver must scope `patient_id`).
- [x] `POST /psychology/physician/clear-gate` — clear `physician_review_required` on profile after review (doctor).
- [x] Added WebSocket streaming endpoint:
  - `WS /psychology/ws/emotion/{patient_id}` (2fps cadence in server loop)
- [x] Implemented full message pipeline structure inside service handler.

### Emotion + Mental State Logic
- [x] Implemented multimodal fusion contract (`label`, `distress_score`, `confidence`, `stress_level`, `sentiment_score`, `modalities_used`).
- [x] Implemented deterministic mental state classifier (Crisis / Depressed / Distressed / Anxious / Neutral).
- [x] Added DeepFace integration hook for face emotion inference with fallback.
- [x] Added SpeechBrain integration hook for speech emotion inference with fallback.
- [x] Append face-frame inference points into the same emotion trend store as chat turns (persistence when DB enabled).

### Crisis Safety Layer
- [x] Implemented crisis short-circuit behavior before normal response flow.
- [x] Implemented safe static crisis response path.
- [x] Implemented crisis event persistence abstraction and retrieval endpoint.
- [x] Sustained distress pattern: rolling window in addition to single-shot `>= 0.75` crisis probability (heuristic text scorer, not XLM-R yet).
- [x] Physician review gate: profile flag, crisis raises gate, `session/start` blocked until cleared via API.

### Data Storage (PostgreSQL — partial vs full architecture)
- [x] Django models + migration: `PsychologyProfile`, `PsychologySession` (UUID `session_id`), `PsychologyMessage`, `PsychologyCrisisEvent`, `PsychologyEmotionLog`.
- [x] FastAPI `psycopg` pool + repositories mirroring those tables (sessions, messages, crises, emotion logs). Falls back to in-memory if pool unavailable.
- [x] Persist full fusion-related metadata per patient message (`fusion_metadata` JSON on `PsychologyMessage`).
- [x] Structured session summary JSON on session row at end (`session_summary_json`).
- [ ] TimescaleDB hypertable + retention policies for `emotion_logs` (currently plain PostgreSQL + index on `(patient_id, logged_at)`).

### Memory Engine
- [x] Long-term patient memory in Qdrant: dedicated collection with `patient_id` payload filter (equivalent to per-patient namespace pattern).
- [x] Hybrid store: Qdrant upsert + in-memory fallback so summaries work without Qdrant.
- [x] Top memories loaded at session start/turn (currently top-5 per turn for continuity context).
- [x] Session end persists summary as JSON string into memory (`emotions_trail`, `risk_flags`, excerpts, etc.).
- [x] `PsychologyProfile` + health/personality context read from PostgreSQL in FastAPI during message handling (not a separate Django HTTP hop).

### Therapy Agent (partial)
- [x] Groq LLM path when `GROQ_API_KEY` is set: strict JSON object (`reply`, `technique`, `recommendation`) with `response_format=json_object`.
- [x] Context assembly from four blocks: CBT Qdrant, patient memory bullets, fusion summary string, profile health JSON + notes.
- [x] Template fallback when Groq is unavailable or returns invalid JSON.
- [ ] Rich recommendation engine (explicit breathing / activity / nutrition / social triggers and content packs beyond current string hints).

### Speech Path (partial)
- [x] API: `speech_transcript` merged into `text` when voice-only payload (`MessageRequest` validator).
- [x] Frontend: Web Speech API → fills chat input (browser STT; FR locale in current UI).
- [ ] Server-side Whisper (or provider) pipeline: audio upload → transcript → emotion branch.
- [ ] Mixed-language (Darija/French/Arabic/English) validation and tuning for voice.

### RAG/Knowledge Base Foundations
- [x] Added curated CBT/ADA/French source manifest from architecture document.
- [x] Added chunking pipeline utilities.
- [x] Added Qdrant client integration for:
  - collection ensure/create
  - indexing chunks
  - semantic search
- [x] Added embedding support using `sentence-transformers` (with deterministic fallback).
- [x] Added KB operations endpoints:
  - `GET /psychology/knowledge/sources`
  - `POST /psychology/knowledge/reindex`
  - `GET /psychology/knowledge/search`
- [x] Added local PDF ingestion from `psychology data/` into Qdrant during reindex (with deterministic IDs and collection reset option in script).
- [x] Added curated source-specific extraction for core psychosocial docs:
  - DDS17 (`DDS_01..DDS_03`)
  - ADA toolkit (`ADA_TK_01..ADA_TK_05`)
  - ADA Section 5 psychosocial slices (`ADA_S5_01..ADA_S5_06`)
  - explicit IDF 2025 exclusion from psychology KB ingest
- [x] Added fail-fast ingestion validation + audit JSON (`tmp/psychology_embed_audit*.json`) with required IDs, min/max char guards, and keyword checks.
- [x] Added extractor switch wiring (`--extractor pypdf|chonkie` and API query param), with safe fallback path.
- [x] Added two-stage retrieval in KB search path:
  - Qdrant vector recall (`top_k` expanded)
  - lexical+metadata reranker with dedupe and source-priority boosts
  - relevance score exposed in retrieval payload for runtime guards
- [x] Added runtime retrieval quality gate (`ok` / `low_score` / `empty`) and safe low-context fallback response.
- [x] Added strict Sanadi LLM contract:
  - stronger system prompt constraints (scope/safety/no diagnosis)
  - required JSON keys with validation (`reply`, `technique`, `recommendation`, `citations`, `safety_mode`)
  - guarded fallback when parse/schema fails
- [x] Language payload tagging in KB chunks (`language` default `en`) to support language-aware retrieval filters as FR/Darija corpora grow.
- [x] Added RAG ops endpoint: `GET /psychology/rag/health` (doctor-only) with collection size, last ingestion timestamp, and retrieval latency p50.

### Frontend Wiring
- [x] Connected psychology dashboard page to backend session/message/trends/crisis APIs.
- [x] Added frontend psychology API client helper (`ack`, `clear-gate`, `psychologyWsBase`).
- [x] Camera capture + JPEG frames → WebSocket `/psychology/ws/emotion/{patient_id}`; live overlay on mood/stress cards.
- [x] Microphone: browser speech-to-text into input (not binary upload to SpeechBrain yet).
- [x] Distress trend line chart (Recharts) from `/trends/{patient_id}` points.
- [x] Clinician workflow: list crisis events, acknowledge, clear session gate for patient on event.

### Hardening (partial)
- [x] Structured logging on key psychology paths (session start, message handling, crisis, session end).
- [x] `GET /health/psychology` — reports Postgres pool availability and Qdrant CBT flag; app lifespan closes DB pool on shutdown.
- [x] FastAPI dependency: `psycopg[binary,pool]` in `fastapi_ai/requirements.txt`.
- [x] WebSocket auth guard on `/psychology/ws/emotion/{patient_id}`:
  - requires valid JWT (query token or cookie)
  - role gate (`patient`, `doctor`)
  - patient self-scope enforcement for patient role
- [x] Added ingestion anomaly checks:
  - min/max chunk length guards
  - keyword presence guards
  - symbol-noise ratio checks
  - chunk-count drift detection against baseline audit snapshot
- [x] Added runtime anomaly flags in message response:
  - retrieval anomalies (`retrieval_empty`, `retrieval_low_score`)
  - LLM anomalies (`llm_parse_fallback`, `llm_missing_citations`, `llm_low_context_fallback`, `llm_crisis_guard_mode`)
  - fusion anomaly (`fusion_abrupt_jump`)
- [x] Graduated safety tiers active in therapy loop:
  - `normal`
  - `elevated_guard`
  - `crisis_guard`
- [x] Session pacing signals active in message pipeline (`opening_checkin`, `working_phase`, `closing_reflection`).
- [x] Technique continuity/progression logic active (state-based therapeutic arc using recent techniques, not per-turn reset).
- [x] Persisted therapist metadata per assistant turn (`technique_used`, `recommendation`, `session_phase`, `safety_mode`) for review.

---

## Missing / Next TODOs (High Priority)

### 1) Data Storage Parity (remaining)
- [ ] TimescaleDB-backed `emotion_logs` hypertable, continuous aggregates, and trend queries tuned for ops.
- [ ] Optional: unify naming with legacy `TherapySession` vs AI `PsychologySession` in product/docs.

### 2) Memory Engine (remaining)
- [ ] Tune Qdrant memory scoring (semantic query vs pure recency scroll) for better “top-3 per turn” relevance.
- [ ] Add retention policy for `patient_memory` (TTL/max-session window + archival path) to prevent long-term vector drift.

### 3) Crisis Engine Completion (spec-level)
- [ ] Replace heuristic crisis scoring with fine-tuned XLM-R (or agreed model) binary classifier endpoint.
- [ ] Physician alert dispatch via Django (signals, notifications, or existing alert app) — not only DB flag.
- [ ] Optional: link crisis rows to assigned care team / routing rules.
- [ ] Add gate timeout/escalation policy (auto-release and/or secondary clinician escalation) to avoid indefinite patient lockout.

### 4) Therapy Agent (remaining)
- [ ] Recommendation engine: structured modules for breathing, activity, nutrition, social support with analytics.
- [ ] Persist citation resolution (`chunk_id -> source/section`) into session artifacts for clinician auditability.

### 5) Speech Path (remaining)
- [ ] Integrate Whisper (or hosted STT) for server-side transcription from uploaded audio.
- [ ] Wire `speech_audio_base64` → transcript → text emotion + SpeechBrain prosody in one tested flow.
- [ ] Add robust browser SpeechRecognition typings/capability fallback to guarantee graceful text-only mode.

### 6) Frontend UX (remaining)
- [x] Authenticate / authorize WebSocket emotion stream (token/cookie JWT + role/scope checks).
- [ ] Optional: upload recorded audio blob to FastAPI for server STT + SpeechBrain when available.

---

## Missing / Next TODOs (Hardening)

### Observability and Safety
- [~] Finer-grained structured logs per pipeline stage (fusion, retrieval, LLM, persist) with safe field names.
- [ ] Request correlation IDs across frontend / FastAPI / Django.
- [ ] Metrics: latency, crisis trigger rate, WS disconnects, retrieval failures.
- [ ] Tests / red-team prompts for crisis safety behavior.

### Security and Compliance
- [ ] PHI redaction policy for logs.
- [ ] Encryption strategy for sensitive therapy content at rest.
- [ ] Immutable audit fields and access controls for crisis records.
- [ ] Rotate exposed secrets and enforce secret-scanning in CI.

### Deployment Hygiene
- [ ] Startup checks: Qdrant reachability, embedding model load, optional DeepFace/SpeechBrain (extend `/health/psychology` or separate readiness).
- [ ] Seed scripts for psychology demo profiles + KB bootstrap in CI/staging.
- [ ] Strict environment validation on FastAPI boot (`QDRANT_*`, `database_url`, model providers) with clear failure messages.
