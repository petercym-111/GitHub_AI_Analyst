"""GitHub workflows: core data first, optional agent work second."""
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from app.configurations.config import settings

from app.crud.analysis_request_log import AnalysisRequestLogCRUD
from app.crud.github_analysis import GitHubAnalysisCRUD
from app.exceptions import AgentExecutionError, OptionalAgentError
from app.services.agent_service import AgentService
from app.services.github_analysis_service import analyze_repositories, get_analysis_version
from app.services.github_services import GitHubService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


async def _with_agent(result: dict, message: str | None, agent: AgentService) -> dict:
    # 3. 可选分支：message 缺失或纯空白时，原样返回已完成的 GitHub 结果。
    if not message or not message.strip():
        return result
    try:
        # 4. 只有主流程成功后才把实际结果传给 Agent loop。
        output = await agent.run(message=message.strip(), endpoint_result=result)
    except AgentExecutionError as exc:
        logger.exception("Optional agent task failed")
        raise OptionalAgentError(result, exc.cause, exc.documents) from exc
    except Exception as exc:
        logger.exception("Optional agent task failed")
        raise OptionalAgentError(result, exc) from exc
    return {**result, "agent": output}


async def get_repositories(
    *, username: str, page: int, per_page: int, message: str | None,
    github_service: GitHubService, agent_service: AgentService,
) -> list[dict] | dict:
    # 1. Repositories 主流程先从 GitHub 读取用户请求的页。
    repos = await github_service.get_user_repos(username, page, per_page)
    if not message or not message.strip():
        # 2. 没有有效 message 就不调用 Agent，直接返回仓库列表。
        return repos
    result = {"username": username, "page": page, "per_page": per_page,
              "repositories": repos}
    # 3. 有 message 时，将分页信息和仓库数据一起作为 Agent context。
    return await _with_agent(result, message, agent_service)


async def get_analysis(
    *, username: str, message: str | None, github_service: GitHubService,
    llm_service: LLMService, agent_service: AgentService, db: AsyncSession,
) -> dict:
    # 1. 缓存有效性由2个条件： time to live(TTL) 和 model/prompt/输入范围版本共同决定。这里会先计算当前版本指纹和 TTL 截止时间
    # TTL 到期：重新分析，即使模型、prompt 和输入范围没变。
    # 版本指纹变化：重新分析，即使缓存还没到期。
    # 两者都没变化：可以复用缓存。

    # 之后数据库查询要求同一条记录同时满足三个条件：
    # GitHubAnalysis.github_username == username
    # GitHubAnalysis.created_at >= cache_cutoff
    # GitHubAnalysis.analysis_version == analysis_version

    start = time.perf_counter()
    analysis_version = get_analysis_version(llm_service.MODEL_NAME)
    cache_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.ANALYSIS_CACHE_TTL_SECONDS
    )
    try:
        # 2. 只复用仍在有效期内且版本匹配的最新分析。
        cached = await GitHubAnalysisCRUD.get_by_username(
            db, username, created_after=cache_cutoff,
            analysis_version=analysis_version,
        )
        if cached:
            # Cache hit 会跳过 GitHub 获取和单次分析 LLM 调用。
            analysis = cached.analysis
            analysis_id = cached.id
        else:
            # 3. Cache miss：获取前 30 个仓库并生成结构化分析。
            repos = await github_service.get_user_repos(username=username, per_page=30)
            analysis = await analyze_repositories(repos, llm_service=llm_service)
            # 4. 在可选 Agent 开始前，先保存仓库快照和已校验的分析结果。
            saved = await GitHubAnalysisCRUD.create(
                db, github_username=username, repo_snapshot=repos,
                analysis=analysis, model_name=llm_service.MODEL_NAME,
                analysis_version=analysis_version,
            )
            analysis_id = saved.id

    except Exception as exc:
        # 主流程失败：先 rollback，再尽力记录失败日志，最后继续抛出原始异常。
        try:
            await db.rollback()
        except Exception:
            logger.exception("Could not roll back failed analysis transaction")
        await _write_request_log(
            db, username=username, analysis_id=None, success=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error_message=type(exc).__name__,
        )
        raise

    # 5. Agent 开始前记录主流程成功；日志写入失败不能丢弃已完成的分析。
    await _write_request_log(
        db, username=username, analysis_id=analysis_id, success=True,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )

    result = {"username": username, "cached": bool(cached), "analysis": analysis}
    # 6. 最后运行可选 Agent；Agent 失败不会撤销主流程结果。
    return await _with_agent(result, message, agent_service)


async def _write_request_log(
    db: AsyncSession,
    *,
    username: str,
    analysis_id: UUID | None,
    success: bool,
    duration_ms: int,
    error_message: str | None = None,
) -> None:
    # 请求日志尽力写入；rollback 或日志异常会被收敛，避免覆盖主流程结果/异常。
    try:
        await AnalysisRequestLogCRUD.create(
            db, github_username=username, analysis_id=analysis_id,
            success=success, duration_ms=duration_ms, error_message=error_message,
        )
    except Exception:
        try:
            await db.rollback()
        except Exception:
            logger.exception("Could not roll back failed request-log transaction")
        logger.exception("Could not write analysis request log")
