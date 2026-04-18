# 📋 Glunova — Feature Matrix & AI Operations

[![ESPRIT](https://img.shields.io/badge/ESPRIT-3IA3-003366)](https://esprit.tn/)
[![Matrix](https://img.shields.io/badge/Content-feature%20matrix-0066cc)](features.md#platform-axes-overview)

Living reference for **platform axes**, **sub-features**, **AI operations**, and **assignments**. For setup and architecture, see the [README](README.md); for backend internals, [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md). RBAC planning: [role_access_plan.md](role_access_plan.md), [rbac_implementation_plan.md](rbac_implementation_plan.md).

**Innova Team • ESPRIT • Class 3IA3 • 2026**

---

## Platform axes overview

| Platform Axis                 | Core AI Purpose                                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| Non-Invasive Screening        | Predict diabetes risk and complications using voice, tongue, and eye data (no blood tests required). |
| Monitoring                    | Continuously monitored patient experience.                                                           |
| Nutrition & Physical Activity | GI-aware meal planning and glucose-safe exercise scheduling via agentic AI.                          |
| Psychology                    | Emotional distress detection and mental health support via AI models.                                |
| Kids Engagement               | Interactive AI-driven features designed for diabetic children.                                       |
| Care Circle                   | AI-coordinated family updates, shared care plans, and caregiver support.                             |
| Clinic Decision Support       | AI-powered complication detection and clinical decision support for clinicians.                      |
| Accessible & Explainable Care | Accessible and explainable patient experience.                                                       |

---

## 1. Non-Invasive Screening

| Sub-Feature           | AI Operation                                                                                                                              | Assigned To      |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| Diabetes via Voice    | Predict diabetes likelihood from acoustic features (pitch, jitter, shimmer, intensity).                                                   | Dhia Mechi       |
| Diabetes via Tongue   | Classify diabetes risk from tongue photograph morphology using image classification.                                                      | Edam Hakim       |
| Voice + Tongue Fusion | Attention-based late fusion of voice and tongue model outputs into a unified diabetes risk score; modality-missing-tolerant architecture. | Edam Hakim       |
| Cataract Detection    | Detect cataract eye disease from fundus/eye images via deep learning classifier.                                                          | Ghofrane Nefissi |

---

## 2. Monitoring

| Sub-Feature                 | AI Operation                                                                                            | Assigned To |
| --------------------------- | ------------------------------------------------------------------------------------------------------- | ----------- |
| Screening History           | Store, retrieve, and visualize longitudinal screening results with AI-detected trend changes over time. | Mo          |
| Risk Stratification         | Classifies each patient into a risk tier (Low / Moderate / High / Critical) based on their health data. | —           |
| Health Alerts               | Proactive AI-generated alerts when risk thresholds are crossed.                                         | —           |
| Disease Progression Tracker | Monitors key health indicators and flags condition changes (worsening, stable, improving).              | —           |

---

## 3. Nutrition & Physical Activity

### 3.1 Nutrition AI Features

| Sub-Feature                          | AI Operation                                                                            | Assigned To |
| ------------------------------------ | --------------------------------------------------------------------------------------- | ----------- |
| Multimodal Meal Logging              | Input via text, barcode, voice, or photo; compute carbs, calories, sugar, GI, GL.       | —           |
| Agentic AI Nutritionist              | RAG pipeline over PubMed and ADA guidelines with tool-calling APIs.                     | —           |
| Context-Aware Food Substitution      | Detect high-GI foods and suggest optimized alternatives using vector similarity search. | —           |
| Adaptive Nutrition Goals & Dashboard | Compute and adjust daily nutrition targets dynamically.                                 | —           |

---

### 3.2 Physical Activity

| Sub-Feature                       | AI Operation                                                          | Assigned To |
| --------------------------------- | --------------------------------------------------------------------- | ----------- |
| Glucose-Aware Exercise Scheduling | Recommend safe, personalized exercise routines based on patient data. | —           |
| Post-Exercise Recovery Advisor    | Generate recovery plan (snack, recheck, next-session prep).           | —           |

---

## 4. Psychology

| Sub-Feature                           | AI Operation                                                   | Assigned To   |
| ------------------------------------- | -------------------------------------------------------------- | ------------- |
| Multimodal Emotion Recognition System | Detect emotional states using text, speech, and facial cues.   | Yessine Hakim |
| AI Therapist Mode ("Sanadi")          | Personalized conversational therapy using adaptive AI.         | Yessine Hakim |
| Longitudinal Trend Monitoring         | Detect long-term negative emotional trends.                    | Yessine Hakim |
| Breathing Mood Animation              | Trigger guided breathing animations for distress reduction.    | Yessine Hakim |
| Physician Crisis Alert                | Escalate severe cases to physicians with structured summaries. | Yessine Hakim |
| Gamified Diabetes Learning            | NLP chatbot with quizzes and adaptive learning.                | Yessine Hakim |

---

## 5. Kids Engagement

| Sub-Feature                   | AI Operation                                  | Assigned To |
| ----------------------------- | --------------------------------------------- | ----------- |
| AI Speech Assistant           | Child-friendly conversational AI.             | —           |
| Lie Detection via Expressions | Detect inconsistencies via facial analysis.   | —           |
| Voice Cloning (Parent Voice)  | Generate reminders using parent voice.        | —           |
| StoryMaker                    | Convert patient photos into gamified avatars. | —           |

---

## 6. Care Circle

| Sub-Feature                          | AI Operation                                             | Assigned To |
| ------------------------------------ | -------------------------------------------------------- | ----------- |
| Family Health Updates                | AI-generated summaries for caregivers.                   | Edam Hakim  |
| Shared Care Plan                     | Unified care plan for patient, family, and clinicians.   | Edam Hakim  |
| Caregiver Support Chatbot            | Provide guidance and explain medical terms.              | Edam Hakim  |
| Appointment Coordinator              | Manage scheduling and reminders.                         | Edam Hakim  |
| Medication Guidance Chatbot          | Provide safe medication guidance with doctor validation. | Edam Hakim  |
| Documents OCR & Understanding System | Extract structured data from medical documents.          | Edam Hakim  |

---

## 7. Clinic Decision Support

| Sub-Feature                         | AI Operation                                    | Assigned To         |
| ----------------------------------- | ----------------------------------------------- | ------------------- |
| Diabetic Retinopathy                | Grade retinal images (0–4 severity).            | Mohamed Ali Ghrissi |
| Foot Ulcer Detection & Segmentation | Detect and segment diabetic ulcers from images. | —                   |
| Plantar Infrared Diabetes Classification               | Predict diabetes using infrared imaging.          | Yessine Hakim       |
| Pre-Consultation Patient Summary    | Generate structured clinical briefings.         | —                   |
| Priority Case Review                | Rank patients by urgency.                       | —                   |

---

## 8. Accessible & Explainable Care

### 8.1 Accessibility

| Sub-Feature               | AI Operation                                      | Assigned To |
| ------------------------- | ------------------------------------------------- | ----------- |
| Voice-Guided Navigation   | Hands-free navigation via speech recognition.     | —           |
| Screen Reader Compliance  | WCAG 2.1 compliant outputs.                       | —           |
| Adaptive Visual Design    | Dynamic UI adjustments (contrast, fonts, colors). | —           |
| Multilingual Support      | Automatic translation of outputs and reports.     | —           |
| Keyboard & Switch Control | Full accessibility via keyboard/switch devices.   | —           |

---

### 8.2 Explainability

| Sub-Feature                   | AI Operation                                                                 | Assigned To |
| ----------------------------- | ---------------------------------------------------------------------------- | ----------- |
| Plain-Language Explainability | Convert AI outputs into patient-friendly explanations using SHAP / Grad-CAM. | All members |

---

**Supervised by:** Mme Jihene Hlel • Mr Fedi Baccar • Mme Widad Askri

**Innova Team • ESPRIT • Class 3IA3 • 2026**

---

## Related docs

- [README.md](README.md) — install, repo layout, service URLs
- [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md) — auth, OCR, screening pipelines
- [role_access_plan.md](role_access_plan.md) · [rbac_implementation_plan.md](rbac_implementation_plan.md) — access model and implementation plan
