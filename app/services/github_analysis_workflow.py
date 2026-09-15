"""Shared use case for the HTTP endpoint and the agent's analysis tool."""

import logging
import time

from sqlalchemy.orm import Session

from app.crud.analysis_request_log import AnalysisRequestLogCRUD
from app.crud.github_analysis import GitHubAnalysisCRUD
from app.schemas.github_analysis import GitHubAnalysisSchema
from app.services.github_analysis_service import analyze_repositories
from app.services.github_services import GitHubService
from app.services.LLM_services import LLMService

logger = logging.getLogger(__name__)


async def get_or_create_analysis(
    username: str,
    *,
    github_service: GitHubService,
    llm_service: LLMService,
    db: Session,
) -> dict:
    # Workflow: cache -> GitHub -> analysis LLM -> persistence -> request log.
    # Both entry points return the same username/cached/analysis payload.
    start = time.perf_counter()
    try:
        cached = await GitHubAnalysisCRUD.get_by_username(db, username)
        if cached:
            analysis = GitHubAnalysisSchema.model_validate(cached.analysis).model_dump()
            result = {"username": username, "cached": True, "analysis": analysis}
            analysis_id = cached.id
        else:
            repos = await github_service.get_user_repos(username=username, per_page=30)
            analysis = await analyze_repositories(repos, llm_service=llm_service)
            saved = await GitHubAnalysisCRUD.create(
                db,
                github_username=username,
                repo_snapshot=repos,
                analysis=analysis,
                model_name=llm_service.MODEL_NAME,
            )
            result = {"username": username, "cached": False, "analysis": analysis}
            analysis_id = saved.id

        await AnalysisRequestLogCRUD.create(
            db,
            github_username=username,
            analysis_id=analysis_id,
            success=True,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return result
    except Exception as exc:
        # A failed transaction needs rollback before attempting a failure log.
        # Logging failure must not replace the original operational error.
        try:
            db.rollback()
            await AnalysisRequestLogCRUD.create(
                db,
                github_username=username,
                analysis_id=None,
                success=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_message=str(exc),
            )
        except Exception:
            logger.exception("Could not persist the analysis failure log")
        raise
