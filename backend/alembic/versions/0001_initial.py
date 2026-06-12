"""Initial schema — all TenderRadar tables + PostgreSQL full-text search.

Revision ID: 0001
Revises:
Create Date: 2026-06-11

This bootstrap migration creates the schema from the ORM metadata so it can
never drift from `app/models.py`. Subsequent migrations should be generated
with `alembic revision --autogenerate -m "..."` as usual.
"""
from typing import Sequence, Union

from alembic import op

from app.database import FTS_DDL, Base
from app import models  # noqa: F401 — register all mappings

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute(FTS_DDL)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_tenders_search_vector ON tenders;")
        op.execute("DROP FUNCTION IF EXISTS tenders_search_vector_update();")
    Base.metadata.drop_all(bind=bind)
