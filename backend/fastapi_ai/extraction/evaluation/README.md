# OCR Evaluation With DeepEval

This package lets you evaluate the full Glunova OCR + structured extraction pipeline with an LLM judge instead of only checking string equality.

It is not limited to lab reports. The same evaluation flow is meant for:

- prescriptions
- lab reports
- general medical reports
- scanned images
- digital PDFs
- any future OCR document type handled by the extraction API

## What gets judged

Each sample is scored on:

- `ocr_fidelity`: whether the OCR transcript preserves the important medical text
- `structured_correctness`: whether the extracted JSON matches the expected fields, values, units, and document type
- `groundedness`: whether the extracted fields are supported by the OCR text
- `document_type_correct`: exact check for the expected document type

## Recommended evaluation design

Yes, this is broadly the right way to do it, but the best practice is:

1. Evaluate the shared OCR pipeline end to end, not a single document family.
2. Build one mixed dataset with examples from every important document type.
3. Include both document-level expectations and field-level gold data.
4. Slice the final report by document type, language, file format, and OCR source.
5. Keep deterministic checks alongside LLM-as-a-Judge, not instead of them.

In other words, use the judge for semantic quality and realism, but still keep exact checks for things like document type, required fields, dates, and clinically important numeric values.

## Dataset format

Use a JSONL file where each line looks like:

```json
{
  "sample_id": "lab-hana-2026-03-31",
  "file_path": "../../MME HANA HAKIM EP BELLAJ  2026_03_31_14_46_16 (1).pdf",
  "mime_type": "application/pdf",
  "expected_document_type": "lab_report",
  "expected_ocr_text": "Optional gold transcript here",
  "expected_extracted_json": {
    "document_type": "lab_report",
    "date": "2026-03-31",
    "labs": [
      { "name": "HbA1c", "value": "5.52", "unit": "%" },
      { "name": "Glucose", "value": "1.06", "unit": "g/L" }
    ]
  },
  "notes": "French lab report"
}
```

`expected_ocr_text` is optional. If you omit it, DeepEval focuses on structured extraction and groundedness.

In a real benchmark, mix samples like:

- prescription with medication names, dosage, frequency, duration
- lab report with analytes, values, units, dates
- medical report with diagnosis, vitals, provider or patient identifiers
- clean digital PDF and noisy scanned image versions of the same type
- multilingual or OCR-noisy documents if your users upload them

## Run

From `backend/fastapi_ai`:

```bash
python scripts/run_extraction_evaluation.py --dataset extraction/evaluation/data/ocr_evalset.jsonl --ocr-backend auto
```

To force Gemini as the DeepEval judge:

```bash
python scripts/run_extraction_evaluation.py --dataset extraction/evaluation/data/ocr_evalset.sample.jsonl --ocr-backend local --judge-provider gemini --judge-model gemini-1.5-pro
```

Set one of these environment variables before running:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

## Notes

- The shared extraction flow lives in `extraction/services/orchestrator.py`, so the API and evaluation runner use the same pipeline.
- The current sample dataset is just an example. Your real eval set should contain multiple document categories, not only labs.
- If `deepeval` is not installed in your environment, the runner falls back to lightweight similarity scoring so the script still works.
- DeepEval commonly expects judge-model credentials in the environment supported by your installed version. If you prefer Groq as the judge, keep the same dataset and swap in a custom judge wrapper later.
