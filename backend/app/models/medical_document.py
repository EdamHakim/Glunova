from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DocumentProcessingStatus, LLMRefinementStatus


class MedicalDocument(Base):
    __tablename__ = "medical_documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    extracted_json_rules: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)

    llm_provider_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    llm_refinement_status: Mapped[LLMRefinementStatus | None] = mapped_column(
        SQLEnum(LLMRefinementStatus, name="llm_refinement_status", native_enum=False),
        nullable=True,
    )

    document_type_detected: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        SQLEnum(DocumentProcessingStatus, name="document_processing_status", native_enum=False),
        default=DocumentProcessingStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship("Patient", back_populates="medical_documents")
    uploaded_by: Mapped["User | None"] = relationship("User", back_populates="uploaded_medical_documents")
