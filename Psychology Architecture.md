# Glunova AI Platform — Psychology Module
**Full Architecture & Implementation Guide**

*Innova Team • ESPRIT • Class 3IA3 • 2026*
*Author: Yessine Hakim • Supervisor: Mme Jihene Hlel • Mr Fedi Baccar*

---

## Executive Summary

**Sanadi (سنَدي)** is Glunova's AI-powered psychology module — a real-time, multimodal mental health companion built specifically for diabetic patients. It detects emotional states through face, voice, and text; conducts CBT-based therapy conversations; monitors psychological trends over time; and escalates crisis situations to clinical staff automatically. The module handles English, French, Tunisian Darija, Arabic, and code-switched input natively. It operates whether the patient's camera is on or off, speaking or typing.

---

## 1. High-Level Architecture

The module follows a layered architecture with a clear separation between the frontend, orchestration, AI services, and data storage layers.

| Layer | Components |
|-------|------------|
| **Frontend** | React — Chat / Voice / Camera UI |
| **Orchestration** | FastAPI AI Gateway — Orchestrator |
| **AI Services** | Emotion Detection • Mental State Classifier • Sanadi Agent • Memory Engine • Crisis Engine • Recommendation Engine |
| **Data Storage** | PostgreSQL • Qdrant • TimescaleDB • Alert System |

---

## 2. Input Modalities & Scenario Handling

The system adapts automatically to which input signals are available. All four scenarios use the same pipeline — unavailable modalities are masked by the fusion gate.

| Scenario | Camera | Microphone | Active Modalities |
|----------|--------|------------|-------------------|
| Camera + Voice | ON | ON | Face + Speech prosody + Text (LLM) |
| Camera + Typing | ON | OFF | Face + Text (LLM) |
| Voice only | OFF | ON | Speech prosody + Text via Whisper (LLM) |
| Text only | OFF | OFF | Text (LLM) only |

---

## 3. AI Service Components

### 3.1 Emotion Detection Service

Detects the patient's emotional state from all available modalities and fuses them into a single distress score that all downstream components consume.

| Branch | Technology | Language Support |
|--------|------------|-----------------|
| Face (camera on) | DeepFace — pre-trained deep CNN AU remapping to 4 classes | Language-agnostic |
| Speech (mic active) | SpeechBrain wav2vec2-IEMOCAP MFCC + prosody features | Language-agnostic |
| Text (always on) | LLM API — EN + Darija + code-switch; returns emotion JSON in Sanadi reply | English + French + Darija + Mixed |

**Fusion output schema:**

```json
{
  "label":           "anxious",       // neutral | anxious | distressed | depressed
  "distress_score":  0.42,            // continuous [0.0 – 1.0]
  "confidence":      0.78,
  "stress_level":    4,               // mapped integer 1–10
  "sentiment_score": -0.4,
  "modalities_used": ["text", "face"]
}
```

> **Fusion gate logic:** The `AttentionGateFusion` layer dynamically weights each modality by its prediction confidence (entropy). Low-confidence modalities (e.g. face branch when camera is at low light) are down-weighted automatically. Unavailable modalities are masked to uniform distribution and excluded from scoring.

---

### 3.2 Mental State Classifier

A deterministic function — not a trained model — that derives the final clinical state label from the emotion fusion output, the crisis classifier result, and the 7-session trend.

```python
def classify_mental_state(
    distress_score: float,  # from fusion gate
    crisis_detected: bool,  # from fine-tuned XLM-R classifier
    trend_slope: float      # from TimescaleDB rolling 7-session window
) -> str:
    if crisis_detected:         return 'Crisis'
    if distress_score >= 0.80:  return 'Depressed'
    if distress_score >= 0.60:  return 'Distressed'
    if distress_score >= 0.35:  return 'Anxious'
    return 'Neutral'
```

| State | Distress Range | Downstream Action |
|-------|---------------|-------------------|
| Neutral | 0.0 – 0.34 | Normal Sanadi response |
| Anxious | 0.35 – 0.59 | Sanadi uses calming CBT tone + breathing suggestion |
| Distressed | 0.60 – 0.79 | Sanadi uses grounding techniques + flags for review |
| Depressed | 0.80 – 0.99 | Sanadi uses supportive CBT + physician soft alert |
| **Crisis** | Classifier ≥ 0.75 | Safe static response + immediate doctor alert |

---

### 3.3 Sanadi Therapy Agent

An LLM-powered conversational therapist using CBT techniques, adaptive memory, and real-time emotion context. Implemented as a LangGraph agent with RAG over a curated clinical knowledge base.

#### Architecture: RAG + LLM (no fine-tuning required)

At every conversation turn, the system assembles a context-rich prompt from four sources:

| Context Block | Content | Storage |
|---------------|---------|---------|
| CBT knowledge base | Therapy techniques, CBT scripts, ADA mental health guidelines, diabetes distress protocols | Qdrant — similarity search per patient message |
| Patient memory | Past session summaries, key personal facts, identified triggers, coping strategies used | Qdrant — top-3 relevant memories per turn |
| Live emotion state | Current distress score, label, modalities active, trend direction | In-context from fusion gate (real-time) |
| Health context | Glucose trends, risk level, complications, medications | PostgreSQL via Django API |

#### Retrieval Quality Layer (implemented alignment)

Sanadi retrieval is a two-stage pipeline:

1. **Recall stage (Qdrant vector search)** — retrieves top-K candidate chunks with multilingual filtering.
2. **Rerank stage (hybrid)** — combines vector score + lexical overlap + source-priority weighting, then deduplicates near-identical text.
3. **Quality guard** — if best relevance is below threshold or no usable context is found, Sanadi switches to **low-context safe mode** (clarifying supportive response, no fabricated guidance).

This prevents low-quality retrieval from silently contaminating therapy prompts.

#### LLM Response Schema

```json
{
  "reply":             "...",         // therapeutic message in patient's language
  "emotion":           "anxious",
  "distress_score":    0.42,
  "language_detected": "darija",      // en | fr | ar | darija | mixed
  "technique_used":    "cognitive_restructuring",
  "recommendation":    "breathing_478" // optional — triggers recommendation engine
}
```

Internal contract hardening:
- System prompt enforces: no diagnosis, no medication prescribing, no hallucinated clinical claims.
- JSON parser validates required keys (`reply`, `technique`, `recommendation`) and optional safety keys (`citations`, `safety_mode`).
- On schema/parse violation, Sanadi falls back to deterministic template response.

#### Multilingual Support

Sanadi handles English, Modern Standard Arabic, Tunisian Darija, French, and code-switched sentences natively through the LLM. No fine-tuning or separate translation layer is required. The model detects the patient's language from each message and responds in kind.

---

### 3.4 Memory Engine

| Memory Type | Implementation |
|-------------|----------------|
| Short-term | Last 10 conversation turns held in LangGraph session state (in-context window). Cleared at session end. |
| Long-term | After each session, Sanadi generates a structured summary (key emotions, triggers, breakthroughs, risk flags). Embedded via sentence-transformers and stored in Qdrant under patient namespace. |
| Retrieval | At session start, top-3 most relevant long-term memories are retrieved via cosine similarity and injected into the system prompt. |
| Profile | Static patient facts (name, age, complication profile, preferred coping strategies) stored in PostgreSQL `psychology_profiles` table. |

---

### 3.5 Crisis Detection Engine

> **Safety design principle:** Crisis detection is the ONLY component where a deterministic ML model (not an LLM) makes the decision. LLMs must never be trusted for safety-critical binary decisions. The crisis classifier fires BEFORE Sanadi generates a response — if crisis is detected, Sanadi receives a safe static template and cannot generate a free-form reply.

| Property | Details |
|----------|---------|
| Model | Fine-tuned XLM-RoBERTa-base — binary classifier (crisis / not-crisis) |
| Training data | CrisisNLP dataset, SuicideWatch Reddit corpus, CLPsych shared task data |
| Languages | English + Arabic + French — XLM-R's cross-lingual transfer handles Darija and French natively |
| Threshold | P(crisis) ≥ 0.75 triggers the alert — tuned for high recall over precision |
| Trigger conditions | Suicide ideation keywords, self-harm intent, severe hopelessness patterns, `distress_score` ≥ 0.85 for 2+ consecutive turns |
| Output | `{ "crisis": true, "severity": "high", "action": "alert_doctor" }` |

#### Crisis Response Flow

1. Crisis classifier fires (before LLM call)
2. Event logged to `crisis_events` table with full message and severity
3. Push notification sent to assigned physician dashboard
4. Care Circle alert sent to designated caregiver
5. Sanadi switches to safe static response — no LLM generation during crisis
6. Session flagged — physician must review before next session is permitted

#### Runtime Anomaly Detection (implemented alignment)

Sanadi emits anomaly flags for clinician-safe observability:

- **Retrieval anomalies:** `retrieval_empty`, `retrieval_low_score`
- **LLM anomalies:** `llm_parse_fallback`, `llm_missing_citations`, `llm_low_context_fallback`, `llm_crisis_guard_mode`
- **Fusion anomalies:** abrupt distress jump (`fusion_abrupt_jump`) between consecutive turns

These are attached to message-level metadata and logs for review and debugging.

---

### 3.6 Recommendation Engine

Triggered by Sanadi when a specific recommendation type is identified in the therapy turn. Generates personalized suggestions using the LLM with patient health context.

| Type | Trigger | Example Output |
|------|---------|----------------|
| Breathing exercise | Anxious state or distress_score 0.35–0.65 | 4-7-8 breathing — inhale 4s, hold 7s, exhale 8s. Animated overlay activated. |
| Physical activity | Stable glucose + low-moderate distress | 15-minute walk recommended — safe given current glucose trend. |
| Nutrition advice | Post-session with high stress | Magnesium-rich snack suggestion — dark chocolate, almonds. |
| Social support | Depressed state or sustained isolation signals | Contact a trusted person. Connects to Care Circle module. |

---

## 4. Model Training Requirements

> **Key principle: train only what must be trained.** Of 6 AI components in the module, only 3 require training a model. The rest are implemented through prompt engineering, RAG, and pure engineering. This is the correct approach — training unnecessarily wastes time and reduces accuracy.

| Component | Approach | Est. Time | Status |
|-----------|----------|-----------|--------|
| Face emotion branch | DeepFace library (pre-trained) — no training needed | 2 hours setup | Use off-the-shelf |
| Speech emotion branch | SpeechBrain wav2vec2 — no training needed | 2 hours setup | Use off-the-shelf |
| Crisis detection | Fine-tune XLM-RoBERTa — CrisisNLP + SuicideWatch data | 1 day | **MUST TRAIN** |
| Text emotion (Sanadi) | LLM JSON side-channel — no training needed | Prompt only | Prompt engineer |
| Mental state classifier | Deterministic function — no ML involved | 1 hour code | Pure engineering |
| Memory engine | Qdrant + PostgreSQL — no ML involved | 1 day | Pure engineering |
| Alert system | Django signals — no ML involved | 1 day | Pure engineering |
| Sanadi agent | RAG + LLM API — no fine-tuning needed | 2–3 days | Prompt + RAG |
| Recommendation engine | LLM with health context — no training needed | 1 day | Prompt engineer |

### Crisis Classifier — Fine-tuning Details

| Property | Value |
|----------|-------|
| Base model | `FacebookAI/xlm-roberta-base` (125M parameters) |
| Task | Binary classification: crisis / not-crisis |
| Training datasets | CrisisNLP (HuggingFace), SuicideWatch Reddit, CLPsych 2015 shared task |
| Languages covered | English, Arabic, French (XLM-R cross-lingual transfer covers Darija and French — no retraining needed) |
| Fine-tuning strategy | Freeze base layers 1–8. Train layers 9–12 + classification head. |
| Decision threshold | P(crisis) ≥ 0.75 — tuned for high recall (missing a crisis is worse than a false alarm) |
| Training time | ~3–4 hours on Google Colab T4 GPU |
| Evaluation metric | F1-score on crisis class (not accuracy — class imbalance) |

---

## 5. Database Design

### 5.1 PostgreSQL — Core Tables (Django models)

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| **psychology_profiles** | user_id, baseline_stress, personality_notes, risk_level, assigned_physician | Static psychological profile per patient. Created at onboarding. |
| **therapy_sessions** | id, patient_id, started_at, ended_at, session_summary, dominant_emotion, avg_distress | One row per Sanadi session. Summary generated by LLM at session end. |
| **messages** | id, session_id, sender, content, emotion_detected, distress_score, mental_state, created_at | Full message log with emotion metadata per message. |
| **emotion_logs** | id, patient_id, emotion, distress_score, stress_level, modalities_used, timestamp | Time-series emotion data. Stored in TimescaleDB for trend queries. |
| **crisis_events** | id, patient_id, severity, detected_text, crisis_score, action_taken, resolved_at, resolved_by | Immutable audit log of every crisis detection event. |

### 5.2 Qdrant — Vector Store Collections

| Collection | Contents |
|------------|---------|
| `cbt_knowledge` | Chunked CBT technique documents, ADA mental health guidelines, diabetes distress protocols. Used for RAG retrieval per patient message. |
| `patient_{id}_memory` | Per-patient long-term memory embeddings. Session summaries, key facts, identified triggers. Retrieved at session start. |
| `crisis_patterns` | Embeddings of known crisis language patterns used as a secondary reference for the crisis classifier (not primary decision). |

---

## 6. API Design (FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/psychology/session/start` | Initialize session, load patient memory, set up LangGraph state. |
| **POST** | `/psychology/message` | Main endpoint — full pipeline: store → detect → classify → crisis check → respond. |
| **POST** | `/psychology/emotion/frame` | Single-frame face emotion from base64 JPEG (non-streaming). |
| **WS** | `/ws/emotion/{patient_id}` | WebSocket for real-time camera emotion streaming at 2fps. |
| **GET** | `/psychology/session/{id}` | Retrieve full session with all messages and emotion metadata. |
| **GET** | `/psychology/trends/{patient_id}` | 7-session rolling emotional trend data from TimescaleDB. |
| **GET** | `/psychology/crisis/events` | List all crisis events (physician dashboard). |
| **POST** | `/psychology/session/end` | Finalize session — trigger LLM summary, store to long-term memory. |

### 6.1 Full Message Request Flow

1. Receive patient message (text typed or Whisper transcript from voice)
2. Store raw message to `messages` table
3. **Run crisis classifier — if P(crisis) ≥ 0.75: trigger safety layer, skip to step 9**
4. Merge text emotion + live face/speech scores → fusion gate → `distress_score`
5. Classify mental state (Neutral / Anxious / Distressed / Depressed)
6. Retrieve relevant CBT chunk from Qdrant (similarity search)
7. Retrieve top-3 patient memories from Qdrant
8. Assemble Sanadi system prompt with all context blocks
9. Call LLM API → receive reply + emotion JSON
10. Store Sanadi response + all emotion metadata to `messages` table
11. Append `distress_score` to `emotion_logs` (TimescaleDB time series)
12. If recommendation triggered: call Recommendation Engine in background
13. Stream reply to frontend via WebSocket

---

## 7. Full Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Face emotion** | DeepFace (Python library) | Pre-trained deep CNN for 7-class facial emotion — remapped to 4 Glunova classes |
| **Speech emotion** | SpeechBrain wav2vec2-IEMOCAP | SOTA speech emotion from prosody — language-agnostic |
| **Speech transcription** | OpenAI Whisper (large-v3) | Real-time transcription — handles Darija + code-switching |
| **Crisis detection** | Fine-tuned XLM-RoBERTa | Binary crisis / not-crisis classifier — only model you train |
| **Sanadi LLM** | GPT-4 API or Claude API | Therapy responses + text emotion detection in one call |
| **Agent orchestration** | LangGraph | Multi-step reasoning, memory state, conversation flow |
| **Vector store** | Qdrant | CBT knowledge base + patient long-term memory |
| **Time series DB** | TimescaleDB (PostgreSQL ext.) | Emotion trend data for longitudinal monitoring |
| **Main database** | PostgreSQL (Django ORM) | Patient profiles, sessions, messages, crisis events |
| **Backend API** | FastAPI (AI services) | WebSocket + async endpoints for all AI inference |
| **Backend platform** | Django (patient/clinic data) | Auth, admin, patient records, appointments |
| **Frontend** | React + TailwindCSS | Chat UI, emotion camera overlay, dashboards |
| **Real-time** | WebSocket (FastAPI) | 2fps camera emotion stream + Sanadi reply streaming |

> **Sanadi is:** AI Therapist • Emotion Analyzer • Risk Detector • Memory-Based Assistant • Care Coordinator
> *English • French • Tunisian Darija • Arabic • Code-switched*

---

## 8. External Data Sources for Sanadi RAG Knowledge Base

The following curated external datasets and clinical resources should be ingested, chunked, and embedded into the Qdrant `cbt_knowledge` collection to power Sanadi's RAG pipeline. All sources are openly accessible and do not require model fine-tuning.

### 8.1 CBT Scripts & Therapy Techniques

### 8.2 ADA Mental Health & Diabetes Guidelines

### 8.3 Diabetes Distress Protocols & Psychoeducation

### 8.4 Ingestion Validation & Drift Controls (implemented alignment)

Before embedding to `cbt_knowledge`, Sanadi runs fail-fast validation:

- required curated chunk IDs per source
- min/max chunk lengths
- keyword presence checks per chunk
- symbol-noise ratio check
- chunk-count drift vs baseline snapshot

Artifacts are written to `backend/fastapi_ai/tmp/psychology_embed_audit*.json` and block ingestion when constraints fail.

---

### 8.5 Care Circle Crisis Notification — Planned Feature

> ⚠️ **Planned: Care Circle Notification on Crisis**
>
> When the care circle notification feature is implemented, the crisis response flow (Section 3.5) will be extended as follows: Step 4 (currently "Care Circle alert sent to designated caregiver") will trigger a push notification to all members of the patient's care circle — family contacts and designated supporters — via the existing Django alert system. The notification payload will include severity level and a safe, non-alarmist message template. No clinical details will be shared without patient consent configuration. The `crisis_events` table already supports this with the `action_taken` field.
>
> **Implementation note:** Add a `care_circle_contacts` table (`patient_id`, `contact_name`, `contact_phone`, `contact_email`, `notify_on_crisis: bool`) and extend the Django crisis signal to fan out notifications via FCM push / SMS.

---

*Confidential — Glunova AI Platform • Psychology Module Architecture*
