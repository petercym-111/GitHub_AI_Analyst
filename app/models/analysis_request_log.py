from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db_session import Base


class AnalysisRequestLog(Base):
    __tablename__ = "analysis_request_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    github_username: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    analysis_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("github_analysis.id"),
        nullable=True,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    duration_ms: Mapped[int] = mapped_column(
        Integer
    )

    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    analysis: Mapped["GitHubAnalysis | None"] = relationship(
        back_populates="requests"
    )