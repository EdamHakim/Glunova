"""Initial schema for Glunova (all ORM tables).

Revision ID: 0001
Revises:
Create Date: 2026-04-13

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.db.base import Base
    import app.models  # noqa: F401 — register mappers

    assert bind.dialect.name == "postgresql", "Glunova targets PostgreSQL (e.g. Supabase)"
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.db.base import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=bind)
