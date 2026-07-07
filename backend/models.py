"""
SQLAlchemy model for storing LLM interaction logs.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from .database import Base


class LLMLog(Base):
    __tablename__ = "llm_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(36), index=True, nullable=False)
    user_question = Column(Text, nullable=False)
    llm_answer = Column(Text, nullable=False)
    sources_count = Column(Integer, default=0)
    client_ip = Column(String(45), nullable=True)
    guardrail_violation = Column(Integer, default=0)
    token_usage = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
