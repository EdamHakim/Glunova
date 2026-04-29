# Glunova AI Platform - OCR & Extraction Module
**Current Architecture and Implementation Guide (Code-Aligned)**

*Innova Team • ESPRIT • Class 3IA3 • 2026*

---

## Executive Summary

The **OCR & Extraction Module** in Glunova is a robust, multi-layered service designed to process medical documents (prescriptions, lab results, clinical notes) and transform them into verified, structured JSON data. It is implemented in `backend/fastapi_ai/extraction/`.

The pipeline employs a **hybrid architecture** combining state-of-the-art cloud OCR, deterministic rule-based engines, LLM-based structured extraction, and clinical database verification (RxNorm). 

### Key Capabilities
- **Adaptive OCR Engine**: Prioritizes Azure Document Intelligence with automatic fallback to local Tesseract OCR.
- **Multimodal LLM Rescue**: Uses Vision-Language Models (Groq Llama-3.2-Vision) if standard OCR yields low-quality text.
- **Deterministic Validation**: Regex-based rules baseline to prevent LLM hallucinations on critical metrics (HbA1c, Blood Pressure).
- **Clinical Verification**: Automated lookup via National Library of Medicine (RxNorm) and Drug-Drug Interaction screening.
- **Automated Observability**: DeepEval/LLM-as-a-judge harnesses for OCR fidelity and structural extraction evaluations.

---

## Architecture Flow

The pipeline orchestrator (`orchestrator.py`) handles documents through 6 sequential phases:

<div id="mmd" style="padding: 1rem 0"></div>
<script type="module">
import mermaid from 'https://esm.sh/mermaid@11/dist/mermaid.esm.min.mjs';
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
await document.fonts.ready;
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  fontFamily: '"Anthropic Sans", sans-serif',
  themeVariables: {
    darkMode: dark,
    fontSize: '13px',
    fontFamily: '"Anthropic Sans", sans-serif',
    lineColor: dark ? '#9c9a92' : '#73726c',
    textColor: dark ? '#c2c0b6' : '#3d3d3a',
    primaryColor: dark ? '#3C3489' : '#EEEDFE',
    primaryTextColor: dark ? '#CECBF6' : '#3C3489',
    primaryBorderColor: dark ? '#534AB7' : '#534AB7',
    secondaryColor: dark ? '#085041' : '#E1F5EE',
    secondaryTextColor: dark ? '#9FE1CB' : '#085041',
    secondaryBorderColor: dark ? '#0F6E56' : '#0F6E56',
    tertiaryColor: dark ? '#3d3d3a' : '#F1EFE8',
    tertiaryTextColor: dark ? '#D3D1C7' : '#444441',
    tertiaryBorderColor: dark ? '#5F5E5A' : '#888780',
    noteBkgColor: dark ? '#444441' : '#FAEEDA',
    noteTextColor: dark ? '#FAC775' : '#633806',
  },
});

const diagram = `flowchart TD
    A([Document Input\\nJPEG / PNG / PDF / TIFF]) --> B

    B[Preprocessing\\nResize · Grayscale · Binarize · Denoise]
    B --> C

    C{Azure OCR\\navailable?}
    C -- Yes --> D[Azure Document Intelligence\\nprebuilt-layout]
    C -- No / quota --> E[Fallback: PyTesseract\\nLocal OCR]
    D --> F{OCR quality\\nacceptable?}
    E --> F

    F -- Low confidence --> G[Vision Rescue\\nGroq Llama-3.2-Vision\\nimage → text]
    F -- OK --> H

    G --> K

    H{Dual-path\\nextraction}
    H --> I[Deterministic Rules\\nRegex for BP · HR · BMI · Dates]
    H --> J[LLM Structured Parsing\\nGroq Llama-3.3-70b\\nDemographics · Dx · Medications]

    I --> L[Merge & Validate\\nConflict resolution: rules override LLM]
    J --> L
    K[Groq Vision Extract\\nSkips rules + LLM paths] --> L

    L --> M[Clinical Verification\\nRxNorm API lookup · DDI screening\\nLLM tie-breaker for ambiguous drugs]

    M --> N{Gating Logic\\nRequires human review?}

    N -- OCR conf < 70%\\nSevere DDI\\nUnverified drugs\\nVision rescue used --> O([Flag for Doctor Review])
    N -- All checks pass --> P([Verified Structured JSON])

    P --> Q[Observability\\nDeepEval · GEval metrics\\nOCR fidelity · Groundedness · Schema accuracy]
`;

const { svg } = await mermaid.render('mmd-svg', diagram);
document.getElementById('mmd').innerHTML = svg;
const el = document.querySelector('#mmd svg');
if (el) { el.style.width = '100%'; el.style.height = 'auto'; }
</script>

---
## Module Breakdown

### 1. Preprocessing (`preprocessing.py`)
- Standardizes incoming file formats (JPEG, PNG, PDF, TIFF).
- Resizes high-resolution images to a normalized DPI.
- Converts to grayscale, applies binarization thresholds, and removes noise to improve structural clarity for OCR algorithms.

### 2. OCR Strategy (`azure_ocr.py` & `local_ocr.py`)
- **Primary Engine (Azure)**: Uses `prebuilt-layout` models via `azure-ai-formrecognizer` to capture text, tables, and bounding boxes.
- **Fallback Engine (Local)**: Uses PyTesseract if Azure is unconfigured, unreachable, or throws quota errors.
- **Quality Analysis**: The output is scanned for low-confidence characteristics (excessive special characters, low string density). If the OCR text is deemed unusable, the pipeline activates **Vision Rescue**.

### 3. Dual-Path Extraction
If the OCR text is healthy, the pipeline splits into two concurrent workflows:

#### A. Deterministic Rules (`extraction_rules.py`)
- Executes strict regular expressions.
- Extracts heavily constrained metrics: *Blood Pressure (e.g., 120/80), Heart Rate, Weight, BMI, Dates*.
- Extremely low hallucination rate; serves as the absolute source of truth.

#### B. LLM Structured Parsing (`groq_extract.py`)
- Analyzes the `raw_ocr` text using Groq's high-speed inference (Llama-3.3-70b-versatile).
- Infers context and extracts: *Patient Demographics, Clinical Notes, Diagnosis, Complex Medication Regimens*.
- Generates field-level "evidence" mapping (pinpointing the exact substring supporting an extracted value).

*(Note: If Vision Rescue was activated, the image is passed directly to `run_groq_vision_extract` using a Llama-Vision model, skipping A and B).*

### 4. Merging and Validation (`merge_validate.py`)
- Fuses the deterministic rule output with the LLM output.
- **Conflict Resolution**: If the LLM hallucinates an HbA1c of 12.0 but the deterministic rule found 8.5, the deterministic rule overrides the LLM output.

### 5. Clinical Verification (`medication_verify.py`)
- Scans all extracted medications against the **National Library of Medicine (RxNorm)** API.
- Generates fuzzy-matched `RxNormCandidate` clusters.
- Re-ranks candidates based on neighboring OCR context (dosage, route, duration).
- If ambiguous, it triggers an LLM tie-breaker to look at surrounding words.
- Executes `check_drug_drug_interactions` on all verified `rxcuis`.

### 6. Review & Gating Logic (`orchestrator.py`)
The pipeline deterministically flags documents requiring human doctor review if:
1. OCR average confidence < 70%.
2. Severe drug interactions are detected.
3. Medications remain unverified/ambiguous.
4. Vision rescue was required.

---

## Observability & Evaluation (`evaluation/`)

The module includes an offline evaluation harness (`run_deepeval_eval.py` & `test_deepeval_runner.py`) using **DeepEval**. 

It uses the `LLM-as-a-Judge` methodology (GEval metrics) to grade the pipeline on:
- **OCR Fidelity**: Did the OCR engine hallucinate or drop medical facts?
- **Structured Correctness**: Did the LLM map the text into the JSON schema accurately?
- **Groundedness**: Did the extracted fields directly originate from the document?
- **Document Type Accuracy**: Was the document properly classified (prescription vs. lab report)?

This evaluation suite handles decommissioned Groq models gracefully via fallback mapping.
