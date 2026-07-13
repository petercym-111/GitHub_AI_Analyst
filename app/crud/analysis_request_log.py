from sqlalchemy.orm import Session

from app.models.analysis_request_log import (
    AnalysisRequestLog,
)


class AnalysisRequestLogCRUD:

    @staticmethod
    async def create(
        db: Session,
        *, # 这个“*”代表后面的参数全部必须使用 keyword argument来传递
            #例如：github_username="torvalds",
            #     analysis_id=None,
            #     success=True,
            #     duration_ms=512,
            #     error_message=None,
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