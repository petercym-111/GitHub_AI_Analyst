"""GitHub workflows: core data first, optional agent work second."""
import logging
import time

from sqlalchemy.orm import Session

from app.crud.analysis_request_log import AnalysisRequestLogCRUD
from app.crud.github_analysis import GitHubAnalysisCRUD
from app.exceptions import OptionalAgentError
from app.services.agent_service import AgentService
from app.services.github_analysis_service import analyze_repositories
from app.services.github_services import GitHubService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


async def _with_agent(result: dict, message: str | None, agent: AgentService) -> dict:
    if not message or not message.strip():
        return result
    try:
        output = await agent.run(message=message.strip(), endpoint_result=result)
    except Exception as exc:
        logger.exception("Optional agent task failed")
        raise OptionalAgentError(result, exc) from exc
    return {**result, "agent": output}


async def get_repositories(
    *, username: str, page: int, per_page: int, message: str | None,
    github_service: GitHubService, agent_service: AgentService,
) -> list[dict] | dict:
    repos = await github_service.get_user_repos(username, page, per_page)
    if not message or not message.strip():
        return repos
    result = {"username": username, "page": page, "per_page": per_page,
              "repositories": repos}
    return await _with_agent(result, message, agent_service)


async def get_analysis(
    *, username: str, message: str | None, github_service: GitHubService,
    llm_service: LLMService, agent_service: AgentService, db: Session,
) -> dict:
    start = time.perf_counter()
    try:
        cached = await GitHubAnalysisCRUD.get_by_username(db, username)
        if cached:
            analysis = cached.analysis
            analysis_id = cached.id
        else:
            repos = await github_service.get_user_repos(username=username, per_page=30)
            analysis = await analyze_repositories(repos, llm_service=llm_service)
            saved = await GitHubAnalysisCRUD.create(
                db, github_username=username, repo_snapshot=repos,
                analysis=analysis, model_name=llm_service.MODEL_NAME,
            )
            analysis_id = saved.id

        await AnalysisRequestLogCRUD.create(
            db, github_username=username, analysis_id=analysis_id, success=True,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:
        # A failed DB transaction/log write must not hide the original failure.
        try:
            if db is not None:
                db.rollback()
            await AnalysisRequestLogCRUD.create(
                db, github_username=username, analysis_id=None, success=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_message=str(exc),
            )
        except Exception:
            logger.exception("Could not save analysis failure log")
        raise

    result = {"username": username, "cached": bool(cached), "analysis": analysis}
    return await _with_agent(result, message, agent_service)
