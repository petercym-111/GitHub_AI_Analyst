from datetime import datetime
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    func,
)

from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db_session import Base

if TYPE_CHECKING:
    from app.models.github_analysis import GitHubAnalysis

# 以下都是最新版本的 Mapped
class AnalysisRequestLog(Base):
    __tablename__ = "analysis_request_log"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    github_username: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    analysis_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
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
        server_default=func.now(),
    )

    analysis: Mapped["GitHubAnalysis | None"] = relationship(
        back_populates="requests"
    )
