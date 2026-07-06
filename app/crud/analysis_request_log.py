from sqlalchemy.orm import Session

from app.models.analysis_request_log import (
    AnalysisRequestLog,
)


class AnalysisRequestLogCRUD:

    @staticmethod
    async def create(
        db: Session,
        *,
        github_username: str,
        analysis_id: str | None,
        success: bool,
        duration_ms: int,
        error_message: str | None = None,
    ) -> AnalysisRequestLog:

        obj = AnalysisRequestLog(
            github_username=github_username,
            analysis_id=analysis_id,
            success=success,
            duration_ms=duration_ms,
            error_message=error_message,
        )

        db.add(obj)

        db.commit()
        db.refresh(obj)

        return obj