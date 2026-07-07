"""
Database setup with SQLAlchemy for LLM interaction logging.

Uses DATABASE_URL env var if set, otherwise constructs a MySQL/MariaDB
connection string from DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
env vars. Falls back to local SQLite when no env configuration is present.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    name = os.getenv("DB_NAME")

    if all([host, port, user, password, name]):
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"

    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    return f"sqlite:///{data_dir / 'llm_logs.db'}"


DATABASE_URL = _build_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from .models import LLMLog  # deferred to avoid circular import at module level

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if not inspector.has_table(LLMLog.__tablename__):
        return

    existing_cols = {c["name"] for c in inspector.get_columns(LLMLog.__tablename__)}
    model_cols = {c.name for c in LLMLog.__table__.columns}

    missing = model_cols - existing_cols
    if not missing:
        return

    print(f"[DB] Adding missing columns to '{LLMLog.__tablename__}': {missing}")

    with engine.connect() as conn:
        for col in LLMLog.__table__.columns:
            if col.name in missing:
                col_type = _sql_type_for(col)
                nullable = "NULL" if col.nullable else "NOT NULL"
                sql = f"ALTER TABLE {LLMLog.__tablename__} ADD COLUMN `{col.name}` {col_type} {nullable}"
                conn.execute(text(sql))
                conn.commit()


def _sql_type_for(column) -> str:
    from sqlalchemy import Integer, String, Text, DateTime

    t = column.type
    if isinstance(t, Integer):
        return "INTEGER"
    if isinstance(t, String):
        return f"VARCHAR({t.length or 255})"
    if isinstance(t, Text):
        return "TEXT"
    if isinstance(t, DateTime):
        return "DATETIME"
    return "TEXT"
