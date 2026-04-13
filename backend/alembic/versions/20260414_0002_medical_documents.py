"""Medical documents for OCR / Care Circle.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medical_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("extracted_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extracted_json_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_provider_used", sa.String(32), nullable=True),
        sa.Column("llm_refinement_status", sa.String(32), nullable=True),
        sa.Column("document_type_detected", sa.String(64), nullable=True),
        sa.Column("processing_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_medical_documents_patient_id", "medical_documents", ["patient_id"])
    op.create_index(
        "ix_medical_documents_uploaded_by_user_id", "medical_documents", ["uploaded_by_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_medical_documents_uploaded_by_user_id", table_name="medical_documents")
    op.drop_index("ix_medical_documents_patient_id", table_name="medical_documents")
    op.drop_table("medical_documents")
