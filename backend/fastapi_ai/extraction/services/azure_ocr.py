"""Azure Document Intelligence OCR service implementation."""

from __future__ import annotations

import logging
from typing import Any

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from core.config import settings

logger = logging.getLogger(__name__)

async def extract_azure_ocr_payload(file_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """
    Extract text using Azure Document Intelligence Read API.
    Returns a payload matching local_ocr structure.
    """
    meta: dict[str, Any] = {
        "mime_type": mime_type,
        "ocr_engine": "azure_read",
        "source": "azure_cloud",
        "used_raster_fallback": False,
        "average_confidence": None,
        "confidence_available": False,
        "low_quality": False,
        "note": None,
    }

    endpoint = settings.azure_document_intelligence_endpoint
    key = settings.azure_document_intelligence_key

    if not endpoint or not key or "your_azure_key_here" in key:
        meta["note"] = "Azure credentials not configured"
        return {"text": "", "meta": meta}

    try:
        async with DocumentIntelligenceClient(
            endpoint=endpoint, 
            credential=AzureKeyCredential(key)
        ) as client:
            poller = await client.begin_analyze_document(
                "prebuilt-read",
                body=file_bytes,
                content_type=mime_type
            )
            result: AnalyzeResult = await poller.result()

            # Process result
            lines = []
            confidences = []
            for page in result.pages:
                if page.lines:
                    for line in page.lines:
                        lines.append(line.content)
                        # Confidence is available at the line level in some models/SDK versions
                        # For Read, it's often per-word, but let's check line
                        if hasattr(line, "confidence") and line.confidence is not None:
                            confidences.append(float(line.confidence))
                
                # Selection marks, tables, etc are skipped here as we only want raw text for Read

            text = "\n".join(lines).strip()
            
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                meta["average_confidence"] = round(avg_conf * 100, 2)
                meta["confidence_available"] = True
                if avg_conf < 0.5:
                    meta["low_quality"] = True
                    meta["note"] = "Azure reported low confidence"

            if not text:
                meta["note"] = "Azure extracted no text"
            
            return {"text": text, "meta": meta}

    except Exception as exc:
        logger.error(f"Azure OCR failed: {exc}", exc_info=True)
        meta["note"] = f"Azure OCR error: {str(exc)}"
        return {"text": "", "meta": meta}
