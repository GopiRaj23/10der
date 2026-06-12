"""SQLAlchemy engine/session setup.

PostgreSQL is the primary target (full-text search via tsvector). The code
also runs on SQLite for lightweight local hacking — FTS degrades to ILIKE.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def is_postgres() -> bool:
    return engine.dialect.name == "postgresql"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Full-text search plumbing (PostgreSQL only). Kept in one place so both
# `init_db()` (dev convenience) and the Alembic migration can apply it.
FTS_DDL = """
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE OR REPLACE FUNCTION tenders_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
      setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('english', coalesce(NEW.description_text, '')), 'B')
   || setweight(to_tsvector('english',
        coalesce(NEW.organisation, '') || ' ' || coalesce(NEW.department, '')), 'C');
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tenders_search_vector ON tenders;
CREATE TRIGGER trg_tenders_search_vector
  BEFORE INSERT OR UPDATE OF title, description_text, organisation, department
  ON tenders FOR EACH ROW EXECUTE FUNCTION tenders_search_vector_update();

CREATE INDEX IF NOT EXISTS ix_tenders_search_vector
  ON tenders USING gin (search_vector);
"""


def init_db() -> None:
    """Create all tables (dev convenience — production uses Alembic)."""
    from . import models  # noqa: F401  (register mappings)

    Base.metadata.create_all(bind=engine)
    if is_postgres():
        with engine.begin() as conn:
            conn.execute(text(FTS_DDL))
