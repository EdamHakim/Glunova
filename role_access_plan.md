# Glunova Role Access Plan

This document defines the recommended role-based access model for the current Glunova platform.

## Roles

- `patient`: person managing their own health journey.
- `doctor`: clinician responsible for assigned patients.
- `caregiver`: family member or supporter linked to a patient.

## Access Principles

- A `patient` can only access their own data.
- A `doctor` can only access data for patients linked through a `CarePlan`.
- A `caregiver` can only access data for patients linked through `PatientCaregiverLink`.
- Frontend visibility should reflect permissions, but backend enforcement is the source of truth.
- Sensitive medical and psychological data should use least-privilege access.

## Permission Levels

- `Full`: can view and act inside the section.
- `Limited`: can view selected information or perform restricted actions.
- `None`: no access.

## Platform Access Matrix

| Section | Patient | Doctor | Caregiver | Notes |
|---|---|---|---|---|
| Dashboard | Full | Full | Full | Content should be filtered to self, assigned patients, or linked patients. |
| Screening | Full | Limited | Limited | Patient performs self-screening; doctor reviews results; caregiver may only view summaries if allowed. |
| Monitoring | Full | Full | Limited | Caregiver should see alerts and adherence summaries, not full clinical detail by default. |
| Nutrition & Activity | Full | Full | Limited | Caregiver may assist with logging and routine support. |
| Psychology | Full | Limited | Limited | Caregiver access should avoid deep therapy details unless explicitly approved. |
| Care Circle | Full | Full | Full | Shared collaboration area for communication, plans, reminders, and updates. |
| Medical Documents | Full | Full | Full | Access must be relationship-scoped and auditable. |
| Clinical Support | None | Full | None | Doctor-only clinical triage and decision support space. |
| Settings | Full | Full | Full | Each user manages only their own preferences and account settings. |

## Section-Level Permissions

### 1. Dashboard

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| View overview cards | Yes | Yes | Yes |
| View personal or assigned trends | Yes | Yes | Limited |
| View patient risk summaries | Self only | Assigned patients only | Linked patients only |
| Access quick actions | Self-service only | Clinical workflow actions | Support workflow actions |

### 2. Screening

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| Upload screening inputs | Yes | No | No |
| Run self-service AI screening | Yes | No | No |
| View screening result summary | Yes | Yes | Limited |
| View explainability output | Yes | Yes | Limited |
| Validate or comment on result | No | Yes | No |

Policy:

- Screening execution should stay patient-only unless a clinician-operated workflow is added later.
- Doctors may review results for assigned patients.
- Caregivers should see only patient-approved summaries, not raw inference detail by default.

### 3. Monitoring

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| View alerts | Yes | Yes | Limited |
| View event timeline | Yes | Yes | Limited |
| View progression charts | Yes | Yes | Limited |
| Manage risk interventions | No | Yes | No |

Policy:

- Doctor access should include all assigned patient monitoring data.
- Caregiver access should focus on actionable support information such as reminders, alerts, and adherence signals.

### 4. Nutrition & Physical Activity

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| Log meals | Yes | Limited | Limited |
| View nutrition intake | Yes | Yes | Limited |
| View GI and GL metrics | Yes | Yes | Limited |
| View exercise plan | Yes | Yes | Yes |
| Use AI nutrition coach | Yes | Limited | Limited |
| Adjust goals and treatment-linked plans | No | Yes | No |

Policy:

- Patients own day-to-day logging.
- Doctors may review and guide nutrition and exercise for assigned patients.
- Caregivers may help with adherence and logging but should not modify clinical goals.

### 5. Psychology

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| Use AI therapist/chat | Yes | No | No |
| View emotional trend summary | Yes | Yes | Limited |
| View crisis alerts | No | Yes | Limited |
| View therapy transcript details | Yes | Limited | None |
| Trigger support exercises | Yes | Yes | Yes |

Policy:

- Psychological content is high-sensitivity.
- Doctors may access summaries, risk flags, and escalation signals for assigned patients.
- Caregivers should only receive minimal support-facing information unless explicit consent rules are defined.

### 6. Care Circle

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| View care team | Yes | Yes | Yes |
| Participate in support chat | Yes | Yes | Yes |
| View shared care plan | Yes | Yes | Yes |
| Edit shared care plan | Limited | Yes | Limited |
| View updates and reminders | Yes | Yes | Yes |
| Coordinate appointments | Limited | Yes | Yes |

Policy:

- Doctors should own medically authoritative updates.
- Patients and caregivers may contribute routine coordination notes and support communication.

### 7. Medical Documents

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| Upload document | Yes | Yes | Yes |
| View extracted summary | Yes | Yes | Yes |
| Download original document | Yes | Yes | Yes |
| View raw OCR text | Yes | Yes | Limited |
| View documents for unrelated patient | No | No | No |

Policy:

- Every document action must be relationship-scoped.
- `doctor` access requires linked `CarePlan`.
- `caregiver` access requires linked `PatientCaregiverLink`.
- Raw OCR text should be treated as higher sensitivity than basic extracted summaries.

### 8. Clinical Support

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| View prioritization queue | No | Yes | No |
| View image analysis queue | No | Yes | No |
| View pre-consultation summaries | No | Yes | No |
| Perform case review actions | No | Yes | No |

Policy:

- This section is doctor-only.
- It should be hidden in the frontend for non-doctors and blocked in backend routes.

### 9. Settings

| Capability | Patient | Doctor | Caregiver |
|---|---|---|---|
| Manage own theme and accessibility | Yes | Yes | Yes |
| Manage own notification settings | Yes | Yes | Yes |
| Manage own privacy settings | Yes | Yes | Yes |
| Manage another user's settings | No | No | No |

## Data Sensitivity Guidance

| Data Type | Sensitivity | Default Access |
|---|---|---|
| General dashboard summaries | Low | Patient, doctor, caregiver within relationship scope |
| Monitoring trends and alerts | Medium | Patient, doctor, limited caregiver |
| Nutrition logs and adherence | Medium | Patient, doctor, limited caregiver |
| Screening inference details and explainability artifacts | Medium to High | Patient, doctor, limited caregiver summary only |
| Medical documents and OCR output | High | Patient, assigned doctor, linked caregiver |
| Psychology transcripts and distress details | Very High | Patient, limited doctor, no caregiver by default |
| Clinical prioritization tools | High | Doctor only |

## Current Platform Mapping

These sections currently exist in the codebase:

- `Dashboard`
- `Screening`
- `Monitoring`
- `Nutrition & Activity`
- `Psychology`
- `Care Circle`
- `Clinical Support`
- `Settings`

Current role models already present in code:

- `patient`
- `doctor`
- `caregiver`

Current relationship models already present in code:

- `CarePlan` for doctor-to-patient assignment
- `PatientCaregiverLink` for caregiver-to-patient linking

## Implementation Priorities

1. Enforce backend authorization on every patient-scoped endpoint using role plus relationship checks.
2. Restrict `Clinical Support` to `doctor` only in both UI and API.
3. Keep `Screening` execution patient-only unless a clinician workflow is intentionally added.
4. Apply partial-visibility rules for caregiver access, especially in monitoring, psychology, and documents.
5. Use this document as the source reference for future RBAC middleware, route guards, and audit logging.

## Assumptions

- The platform currently supports only three roles.
- A doctor should never access a patient without an explicit assignment.
- A caregiver should never access a patient without an explicit link.
- Caregiver access to psychology and raw document content should remain narrower than doctor access.
