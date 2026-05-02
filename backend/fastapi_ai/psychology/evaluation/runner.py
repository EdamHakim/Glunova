from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psychology.evaluation.dataset_schema import EvalSample
from psychology.kb_retrieval import resolve_kb_retrieval_limit
from psychology.knowledge_ingestion import get_knowledge_base
from psychology.schemas import MessageRequest
from psychology.service import PsychologyService


@dataclass(slots=True)
class EvalRuntimeRow:
    sample_id: str
    question: str
    expected_answer: str
    answer: str
    recommendation: str | None
    technique_used: str
    retrieval_quality: str
    anomaly_flags: list[str]
    contexts: list[str]
    context_ids: list[str]
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "answer": self.answer,
            "recommendation": self.recommendation,
            "technique_used": self.technique_used,
            "retrieval_quality": self.retrieval_quality,
            "anomaly_flags": list(self.anomaly_flags),
            "contexts": list(self.contexts),
            "context_ids": list(self.context_ids),
            "tags": list(self.tags),
        }


def run_samples(samples: list[EvalSample]) -> list[EvalRuntimeRow]:
    service = PsychologyService()
    kb = get_knowledge_base()
    rows: list[EvalRuntimeRow] = []
    for sample in samples:
        session = service.start_session(sample.patient_id, sample.preferred_language)
        if not session.session_id:
            raise RuntimeError(f"Session not started for sample {sample.sample_id}")

        message_payload = MessageRequest(
            session_id=session.session_id,
            patient_id=sample.patient_id,
            text=sample.question,
        )
        response = service.handle_message(message_payload)
        kb_limit = resolve_kb_retrieval_limit(sample.question, response.mental_state)
        kb_items = kb.search(sample.question, language=sample.preferred_language, limit=kb_limit)
        contexts = [str(item.get("text") or "") for item in kb_items]
        context_ids = [str(item.get("chunk_id") or item.get("source") or "unknown") for item in kb_items]
        rows.append(
            EvalRuntimeRow(
                sample_id=sample.sample_id,
                question=sample.question,
                expected_answer=sample.expected_answer,
                answer=response.reply,
                recommendation=response.recommendation,
                technique_used=response.technique_used,
                retrieval_quality=response.retrieval_quality,
                anomaly_flags=list(response.anomaly_flags),
                contexts=contexts,
                context_ids=context_ids,
                tags=sample.tags or [],
            )
        )
        service.end_session(session.session_id, sample.patient_id)
    return rows

