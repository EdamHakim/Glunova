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
- [x] Added WebSocket streaming endpoint:
  - `WS /psychology/ws/emotion/{patient_id}` (2fps cadence in server loop)
- [x] Implemented full message pipeline structure inside service handler.

### Emotion + Mental State Logic
- [x] Implemented multimodal fusion contract (`label`, `distress_score`, `confidence`, `stress_level`, `sentiment_score`, `modalities_used`).
- [x] Implemented deterministic mental state classifier (Crisis / Depressed / Distressed / Anxious / Neutral).
- [x] Added DeepFace integration hook for face emotion inference with fallback.
- [x] Added SpeechBrain integration hook for speech emotion inference with fallback.

### Crisis Safety Layer
- [x] Implemented crisis short-circuit behavior before normal response flow.
- [x] Implemented safe static crisis response path.
- [x] Implemented crisis event persistence abstraction and retrieval endpoint.

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

### Frontend Wiring
- [x] Connected psychology dashboard page to backend session/message/trends/crisis APIs.
- [x] Added frontend psychology API client helper.

---

## Missing / Next TODOs (High Priority)

### 1) Data Storage Parity with Architecture
- [ ] Replace in-memory stores with real PostgreSQL-backed repositories for:
  - `psychology_profiles`
  - `therapy_sessions`
  - `messages`
  - `crisis_events`
- [ ] Implement TimescaleDB-backed `emotion_logs` table/hypertable and trend queries.
- [ ] Persist full emotion metadata per message as defined in architecture.

### 2) Memory Engine Completion
- [ ] Implement long-term patient memory in Qdrant as dedicated per-patient namespace (`patient_{id}_memory` pattern or equivalent filter key).
- [ ] Implement retrieval of top-3 patient memories at session start and per turn.
- [ ] Persist session summaries at session end using structured schema (emotions, triggers, breakthroughs, risk flags).
- [ ] Add `psychology_profiles` model and retrieval path from Django API for health/personality context.

### 3) Crisis Engine Completion (Spec-Level)
- [ ] Replace placeholder crisis scoring with fine-tuned XLM-R binary classifier endpoint.
- [ ] Enforce threshold and trigger conditions from architecture (`>=0.75`, sustained distress patterns).
- [ ] Implement physician alert dispatch via Django alert system (actual signal/event integration).
- [ ] Enforce "physician review required before next session" gate logic.

### 4) Therapy Agent Completion
- [ ] Replace template response generator with real LLM orchestration call and strict JSON response schema.
- [ ] Implement true context assembly from four blocks:
  - CBT knowledge retrieval (Qdrant)
  - patient memory retrieval (Qdrant)
  - live emotion state (fusion output)
  - health context (Django/PostgreSQL)
- [ ] Add recommendation engine trigger handling for breathing/activity/nutrition/social support.

### 5) Speech Path Completion
- [ ] Integrate Whisper transcription path for voice-only scenario.
- [ ] Ensure voice flow: audio -> transcript -> text emotion + speech prosody branch.
- [ ] Validate mixed-language (Darija/French/Arabic/English) handling for voice transcripts.

### 6) Frontend UX Completion (Architecture Parity)
- [ ] Add real camera capture + frame streaming integration into `/ws/emotion/{patient_id}`.
- [ ] Add microphone capture and upload flow for speech emotion/transcription.
- [ ] Add emotion overlay and richer distress trend charting in UI.
- [ ] Add clinician dashboard workflow for reviewing crisis events and session flags.

---

## Missing / Next TODOs (Hardening)

### Observability and Safety
- [ ] Add structured logs for each stage in message pipeline.
- [ ] Add request correlation IDs across frontend/FastAPI/Django.
- [ ] Add metrics (latency, crisis trigger rate, WS disconnects, retrieval failures).
- [ ] Add tests/red-team prompts for crisis safety behavior.

### Security and Compliance
- [ ] Add PHI redaction policy for logs.
- [ ] Add encryption strategy for sensitive therapy content.
- [ ] Add immutable audit fields and access controls for crisis records.
- [ ] Rotate exposed secrets and enforce secret-scanning in CI.

### Deployment Hygiene
- [ ] Add startup health checks for Qdrant/model dependencies.
- [ ] Add migration + seed scripts for psychology schema and KB bootstrapping.
- [ ] Add environment validation for required keys (`QDRANT_*`, DB URLs, model providers).

---

## Suggested Execution Order

- [ ] **Sprint 1:** Real DB persistence + Timescale trends + profile integration.
- [ ] **Sprint 2:** Crisis classifier model integration + alert dispatch + session gating.
- [ ] **Sprint 3:** Full LLM therapy orchestration + patient memory retrieval loop.
- [ ] **Sprint 4:** Voice/camera UI integration + clinician dashboard polish.
- [ ] **Sprint 5:** Observability, security hardening, and release validation matrix.
