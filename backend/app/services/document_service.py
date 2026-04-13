from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.medical_document import MedicalDocument
from app.models.user import User
from app.repositories import medical_document_repo
from app.services import access
from app.services.document_ocr import pipeline as document_pipeline


async def create_document_for_patient(
    db: Session,
    user: User,
    patient_id: UUID,
    file: UploadFile,
) -> MedicalDocument:
    if not access.can_access_patient(user, patient_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this patient")

    content = await file.read()
    mime = file.content_type or "application/octet-stream"

    try:
        result = document_pipeline.process_uploaded_file(
            patient_id, content, file.filename or "upload", mime
        )
    except Exception as e:
        from app.core.exceptions import GlunovaException

        if isinstance(e, GlunovaException):
            raise HTTPException(status_code=e.status_code, detail=e.message) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed",
        ) from e

    row = MedicalDocument(
        patient_id=patient_id,
        uploaded_by_user_id=user.id,
        original_filename=file.filename or "upload",
        mime_type=mime,
        storage_path=result["storage_path"],
        raw_ocr_text=result["raw_ocr_text"],
        extracted_json=result["extracted_json"],
        extracted_json_rules=result["extracted_json_rules"],
        llm_provider_used=result["llm_provider_used"],
        llm_refinement_status=result["llm_refinement_status"],
        document_type_detected=result["document_type_detected"],
        processing_status=result["processing_status"],
        error_message=result["error_message"],
    )
    return medical_document_repo.create(db, row)


def get_document(db: Session, doc_id: UUID, user: User) -> MedicalDocument:
    row = medical_document_repo.get_by_id(db, doc_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not access.can_access_patient(user, row.patient_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this document")
    return row


def list_documents(
    db: Session,
    user: User,
    patient_id: UUID,
    offset: int,
    limit: int,
) -> tuple[list[MedicalDocument], int]:
    if not access.can_access_patient(user, patient_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this patient")
    return medical_document_repo.list_for_patient(db, patient_id, offset, limit)


def hide_raw_for_role(user: User) -> bool:
    return user.role == UserRole.CAREGIVER
