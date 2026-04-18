# 🔐 Glunova RBAC Implementation Plan

[![Scope](https://img.shields.io/badge/Scope-RBAC-555555)](README.md)

This document turns the role access matrix into a concrete implementation plan for the current codebase.

**Related:** [README](README.md) · [features.md](features.md) · [role_access_plan.md](role_access_plan.md)

---

## Goal

Apply reliable role-based and relationship-based access control across the platform for:

- `patient`
- `doctor`
- `caregiver`

The backend must be the source of truth. The frontend should mirror permissions for usability, but never replace backend authorization.

## Current State Summary

### Roles already implemented

- Django user role field in `backend/django_app/users/models.py`
- Frontend session user role in `frontend/lib/auth.ts`
- FastAPI JWT role checks in `backend/fastapi_ai/core/rbac.py`

### Relationship models already implemented

- Doctor to patient assignment via `CarePlan` in `backend/django_app/clinical/models.py`
- Caregiver to patient link via `PatientCaregiverLink` in `backend/django_app/documents/models.py`

### Current gaps

- Frontend navigation only partially hides pages by role.
- Most dashboard pages are visible to all authenticated users.
- Django document endpoints do not consistently enforce doctor and caregiver relationship checks.
- Some FastAPI endpoints validate role, but not whether the actor is allowed to act on the requested `patient_id`.
- The current implementation has no centralized permission helper shared across all backend domains.

## Target Authorization Model

Each protected action should validate:

1. Is the user authenticated?
2. Does the user have the required role?
3. If the action targets a patient record, is that patient in scope for this actor?

Patient scope rules:

- `patient`: only self
- `doctor`: only assigned patients through `CarePlan`
- `caregiver`: only linked patients through `PatientCaregiverLink`

## Implementation Phases

## Phase 1: Centralize Relationship Checks In Django

### Objective

Create reusable permission helpers so every Django endpoint uses the same patient-scope logic.

### Files to update

- `backend/django_app/documents/access.py`
- optionally add `backend/django_app/core/permissions.py`

### Tasks

- Promote patient-scope checks into shared helper functions, for example:
  - `can_access_patient(actor, patient_pk)`
  - `can_view_patient_documents(actor, patient_pk)`
  - `can_upload_patient_documents(actor, patient_pk)`
  - `can_view_patient_psychology(actor, patient_pk)`
- Keep `documents/access.py` if you want document-specific rules, but move generic patient relationship logic to a more central location.
- Use one consistent relationship source:
  - `CarePlan` for doctor scope
  - `PatientCaregiverLink` for caregiver scope

### Deliverable

A single reusable authorization layer for Django views.

## Phase 2: Fix Django Document Authorization

### Objective

Bring medical document APIs in line with the intended access policy.

### Files to update

- `backend/django_app/documents/views.py`
- `backend/django_app/documents/access.py`

### Required changes

#### `DocumentListCreateView.get`

Replace the current patient-only check with a real relationship check.

Current issue:

- Doctors and caregivers are not properly restricted to linked patients.

Target behavior:

- patient can list only their own documents
- doctor can list documents only for assigned patients
- caregiver can list documents only for linked patients

#### `DocumentListCreateView.post`

Add authorization before document creation.

Current issue:

- Upload is allowed as long as `patient_id` is supplied.

Target behavior:

- patient can upload for self only
- doctor can upload for assigned patients only
- caregiver can upload for linked patients only
- `uploaded_by` should be populated with `request.user`

#### `DocumentDetailView.get`

Current issue:

- Only patient mismatch is blocked.

Target behavior:

- any actor must pass patient-scope check against `doc.patient_id`

#### `DocumentDownloadView.get`

Current issue:

- Only patient mismatch is blocked.

Target behavior:

- any actor must pass patient-scope check against `doc.patient_id`

### Optional improvements

- Add audit logging for upload and download actions
- Add response filtering for high-sensitivity fields such as raw OCR text

### Deliverable

Document APIs that actually enforce patient relationship boundaries.

## Phase 3: Add Frontend Route and Navigation Guards

### Objective

Make the UI reflect permissions clearly and prevent users from navigating into sections they should not use.

### Files to update

- `frontend/components/layout/sidebar.tsx`
- `frontend/components/auth/auth-guard.tsx`
- optionally add `frontend/components/auth/role-guard.tsx`
- dashboard page files under `frontend/app/dashboard/*`

### Required changes

#### Sidebar

Current state:

- `Screening` is hidden for non-patients
- other menu items are broadly visible

Target behavior:

- `Screening`: patient only
- `Clinical Support`: doctor only
- `Care Circle`: all roles
- `Monitoring`: all roles, but role-specific content
- `Nutrition & Activity`: all roles, but role-specific actions
- `Psychology`: all roles, but role-specific actions

Suggested menu metadata:

- `allowedRoles: ['patient']`
- `allowedRoles: ['doctor']`
- `allowedRoles: ['patient', 'doctor', 'caregiver']`

#### Route guard

Add a reusable `RoleGuard` or page-level role wrapper for pages that should be blocked entirely.

Pages to hard-block:

- `frontend/app/dashboard/screening/page.tsx`: patient only
- `frontend/app/dashboard/clinical/page.tsx`: doctor only

Pages to keep shared but role-shaped:

- `frontend/app/dashboard/monitoring/page.tsx`
- `frontend/app/dashboard/nutrition/page.tsx`
- `frontend/app/dashboard/psychology/page.tsx`
- `frontend/app/dashboard/care-circle/page.tsx`

### Deliverable

A UI that matches the platform access model and reduces accidental misuse.

## Phase 4: Enforce Patient Scope In FastAPI

### Objective

Do not rely only on role checks for AI endpoints that accept a `patient_id`.

### Files to update

- `backend/fastapi_ai/core/rbac.py`
- `backend/fastapi_ai/nutrition/router.py`
- `backend/fastapi_ai/psychology/router.py`
- `backend/fastapi_ai/kids/router.py`
- optionally add shared scope helper in `backend/fastapi_ai/core`

### Current state

- `screening/router.py` is patient-only and derives patient identity from token claims
- `clinic/router.py` is doctor-only
- `nutrition/router.py` checks role, but not whether the requested `patient_id` belongs to the actor
- `psychology/router.py` checks role, but not patient relationship
- `kids/router.py` checks role, but not patient relationship

### Recommended approaches

#### Option A: Backend-to-backend relationship lookup

FastAPI verifies doctor and caregiver patient scope against shared database models or a trusted Django API.

Pros:

- strongest and most complete

Cons:

- more implementation work

#### Option B: Keep patient-scoped endpoints patient-only for now

If an endpoint cannot yet validate cross-user scope properly, restrict it temporarily.

Examples:

- keep `nutrition/analyze-meal` patient-only until assignment checks exist
- keep `psychology/emotion-detect` patient-only or doctor-only with explicit patient validation
- keep `kids/story` limited to patient only until caregiver scoping is enforced

### Recommended short-term plan

- keep `screening` patient-only
- keep `clinic` doctor-only
- restrict `nutrition`, `psychology`, and `kids` to the narrowest safe role set until patient-scope checks are implemented

### Deliverable

FastAPI endpoints that cannot be used across unrelated patients.

## Phase 5: Define Field-Level Visibility Rules

### Objective

Support partial access instead of only full-page allow or deny.

### Areas needing field-level filtering

- psychology
- monitoring
- medical documents
- care circle updates

### Recommended rules

#### Psychology

- patient: full access to own conversational content
- doctor: summary, trends, crisis alerts, support-needed flags
- caregiver: minimal status indicators only if explicitly allowed

#### Medical documents

- patient: full access
- doctor: full access for assigned patients
- caregiver: extracted summary by default, raw OCR text only if policy allows

#### Monitoring

- patient: full self-view
- doctor: full assigned-patient view
- caregiver: alerts, adherence, routine summaries, no advanced clinical internals by default

### Deliverable

Safer caregiver access and clearer privacy boundaries.

## Phase 6: Align Documentation With Actual Enforcement

### Objective

Remove mismatches between the architecture docs and the implemented permissions.

### Files to update

- `backend/ARCHITECTURE.md`
- `role_access_plan.md`
- API docs or README files if needed

### Current mismatch example

- `backend/ARCHITECTURE.md` mentions screening route RBAC as `patient`, `doctor`
- `backend/fastapi_ai/screening/router.py` currently enforces `patient` only

### Deliverable

Docs that match production behavior.

## Recommended File-by-File Plan

### Django backend

1. `backend/django_app/documents/access.py`
   - centralize relationship-based patient access checks

2. `backend/django_app/documents/views.py`
   - apply helpers to list, upload, detail, and download actions
   - set `uploaded_by`
   - optionally redact raw OCR text for caregiver responses

3. `backend/django_app/clinical/models.py`
   - keep as relationship source for doctor assignment

4. `backend/django_app/core`
   - optionally add shared permissions module

### FastAPI backend

1. `backend/fastapi_ai/core/rbac.py`
   - extend beyond simple role checks if you want actor-to-patient scoping

2. `backend/fastapi_ai/screening/router.py`
   - keep patient-only unless clinician workflow is intentionally added

3. `backend/fastapi_ai/nutrition/router.py`
   - add patient-scope validation or reduce allowed roles

4. `backend/fastapi_ai/psychology/router.py`
   - add patient-scope validation and field-level output rules

5. `backend/fastapi_ai/kids/router.py`
   - add caregiver relationship validation

6. `backend/fastapi_ai/clinic/router.py`
   - keep doctor-only

### Frontend

1. `frontend/components/layout/sidebar.tsx`
   - move from `patientOnly` to generic `allowedRoles`

2. `frontend/components/auth`
   - add a role guard component

3. `frontend/app/dashboard/screening/page.tsx`
   - keep patient-only UX

4. `frontend/app/dashboard/clinical/page.tsx`
   - enforce doctor-only UI access

5. `frontend/app/dashboard/monitoring/page.tsx`
   - render role-specific views and actions

6. `frontend/app/dashboard/nutrition/page.tsx`
   - render role-specific actions

7. `frontend/app/dashboard/psychology/page.tsx`
   - hide high-sensitivity details from caregiver view

8. `frontend/app/dashboard/care-circle/page.tsx`
   - make features patient-context aware

9. `frontend/components/care-circle/medical-documents-section.tsx`
   - reflect backend restrictions and optionally hide raw OCR for caregiver role

## Suggested Delivery Order

1. Fix Django document authorization
2. Restrict frontend navigation and add route guards
3. Lock down doctor-only and patient-only pages
4. Tighten FastAPI patient-scoped endpoints
5. Add field-level filtering for sensitive data
6. Align docs and test coverage

## Testing Plan

Create tests for:

- patient cannot access another patient's records
- doctor cannot access unassigned patient records
- caregiver cannot access unlinked patient records
- doctor can access assigned patient documents
- caregiver can access linked patient documents
- non-doctor cannot open `Clinical Support`
- non-patient cannot run `Screening`

Suggested locations:

- `backend/django_app/documents/tests/`
- add new auth or permission tests for Django APIs
- add FastAPI route tests if the project already uses them

## Recommended Short-Term Decisions

- Treat `Clinical Support` as doctor-only immediately
- Keep `Screening` patient-only immediately
- Restrict ambiguous AI endpoints until patient-scope validation exists
- Avoid exposing psychology transcript detail to caregivers by default

## Outcome

After these changes, the platform will move from basic role labeling to real authorization based on:

- role
- patient relationship
- data sensitivity
- page and endpoint intent
