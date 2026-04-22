# OCR Feature Documentation

This document explains how the OCR feature works in Glunova for medical document processing.

## What the OCR feature does

The OCR flow converts uploaded medical documents (images or PDFs) into machine-readable text, then passes that text into the extraction pipeline that builds structured medical data.

Supported formats:

- `image/jpeg`
- `image/png`
- `image/webp`
- `application/pdf`

## High-level flow

1. A document is uploaded from Django (`documents` app).
2. Django forwards the file to FastAPI AI at `POST /extraction/extract`.
3. FastAPI preprocesses images for better OCR quality.
4. FastAPI performs OCR using Azure Document Intelligence (`prebuilt-layout`).
5. OCR text and OCR metadata are passed to extraction, validation, and enrichment steps.
6. Results are returned to Django and persisted in `MedicalDocument`.

## OCR pipeline components

### 1) Upload and delegation (Django)

`backend/django_app/documents/services/pipeline.py`

- Validates MIME type and upload size.
- Uploads file to storage.
- Calls FastAPI AI service (`/extraction/extract`) with a short-lived service JWT.
- Stores returned OCR text in `MedicalDocument.raw_ocr_text`.

### 2) Preprocessing (FastAPI)

`backend/fastapi_ai/extraction/services/preprocessing.py`

For images, preprocessing applies:

- grayscale conversion
- upscaling if image dimensions are too small
- denoising (median blur)
- contrast enhancement (CLAHE)
- deskewing

For PDFs, bytes are passed as-is to OCR.

### 3) OCR engine (FastAPI)

`backend/fastapi_ai/extraction/services/azure_ocr.py`

Current production OCR path is Azure-only:

- Uses `DocumentIntelligenceClient`
- Model: `prebuilt-layout`
- Returns:
  - extracted raw text (`text`)
  - OCR metadata (`meta`), including confidence and quality flags

Required env vars:

- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`
- `AZURE_DOCUMENT_INTELLIGENCE_KEY`

If credentials are missing, OCR returns empty text and a note in metadata (`"Azure credentials not configured"`).

## OCR metadata and quality signals

The OCR step produces metadata used by downstream logic:

- `ocr_engine`: `"azure_read"`
- `source`: `"azure_cloud"`
- `average_confidence`: OCR confidence (when available)
- `confidence_available`: whether confidence could be calculated
- `low_quality`: quality risk flag
- `note`: optional diagnostic message

`low_quality` can be raised when:

- Azure confidence is low
- no text is extracted
- OCR execution fails

## How OCR quality affects extraction

`backend/fastapi_ai/extraction/router.py`

- If document is an image and OCR is low quality (or empty), the pipeline may switch to vision-based extraction (`run_groq_vision_extract`).
- Otherwise it uses text-based extraction (`run_groq_structured_extract`).
- `review_required` is set when OCR confidence is low, OCR quality is poor, text is missing, drug interactions exist, or medications are unverified.

This ensures uncertain OCR outcomes are flagged for human review.

## API endpoints related to OCR

- `POST /extraction/extract`  
  Main pipeline endpoint that includes OCR + extraction + validation.

- `GET /extraction/health`  
  Returns service health and whether Azure OCR credentials are configured (`azure_ready`).

## Persistence in Django

After FastAPI returns, Django stores:

- `raw_ocr_text`
- `extracted_json`
- `extracted_json_rules`
- `document_type_detected`
- processing / refinement statuses

This allows UI and monitoring features to show extracted content and review status.

## Notes for developers

- There is also a local Tesseract implementation in `backend/fastapi_ai/extraction/services/local_ocr.py`, but the active extraction route currently uses Azure OCR.
- If you want local fallback in production flow, wire `local_ocr.py` into `router.py` as a fallback path when Azure is unavailable.
