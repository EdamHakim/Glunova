from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.medical_document import MedicalDocument
from app.models.user import User
from app.schemas.documents import MedicalDocumentRead
from app.services import document_service
from app.utils.pagination import PaginatedResponse, PaginationParams, offset_limit

router = APIRouter()


def _to_read(doc: MedicalDocument, user: User) -> MedicalDocumentRead:
    r = MedicalDocumentRead.model_validate(doc)
    if document_service.hide_raw_for_role(user):
        return r.model_copy(update={"raw_ocr_text": None})
    return r


@router.post("", response_model=MedicalDocumentRead, status_code=201)
async def upload_document(
    patient_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalDocumentRead:
    doc = await document_service.create_document_for_patient(db, user, patient_id, file)
    return _to_read(doc, user)


@router.get("", response_model=PaginatedResponse[MedicalDocumentRead])
def list_documents(
    patient_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[MedicalDocumentRead]:
    off, lim = offset_limit(pagination.page, pagination.page_size)
    rows, total = document_service.list_documents(db, user, patient_id, off, lim)
    items = [_to_read(r, user) for r in rows]
    return PaginatedResponse.from_sequence(
        items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.get("/{document_id}", response_model=MedicalDocumentRead)
def get_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalDocumentRead:
    doc = document_service.get_document(db, document_id, user)
    return _to_read(doc, user)
