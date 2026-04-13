from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.medical_document import MedicalDocument


def create(db: Session, row: MedicalDocument) -> MedicalDocument:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_by_id(db: Session, doc_id: UUID) -> MedicalDocument | None:
    return db.get(MedicalDocument, doc_id)


def list_for_patient(
    db: Session, patient_id: UUID, offset: int, limit: int
) -> tuple[list[MedicalDocument], int]:
    total = (
        db.scalar(
            select(func.count()).select_from(MedicalDocument).where(
                MedicalDocument.patient_id == patient_id
            )
        )
        or 0
    )
    q = (
        select(MedicalDocument)
        .where(MedicalDocument.patient_id == patient_id)
        .order_by(MedicalDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(q).all()), total
