import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.database.dependencies import get_db
from app.exceptions import OptionalAgentError
from app.routes.error_handlers import optional_agent_response, to_http_exception
from app.services.agent_service import AgentService
from app.services.github_services import GitHubService, get_github_service
from app.services.github_workflow_service import get_analysis
from app.services.llm_service import LLMService

router = APIRouter(tags=["LLM Analysis"])
logger = logging.getLogger(__name__)


@router.post("/users/{username}/analysis")
async def analyze_user_repositories(
    username: str,
    message: str | None = Query(default=None, max_length=4000),
    github_service: GitHubService = Depends(get_github_service),
    llm_service: LLMService = Depends(LLMService),
    agent_service: AgentService = Depends(AgentService),
    db: AsyncSession = Depends(get_db),
):
    # Endpoint owns HTTP input/output; the service owns the workflow.
    try:
        # 1. 执行缓存/获取/分析/保存/日志流程，之后才进入可选 Agent 分支。
        return await get_analysis(
            username=username, message=message, github_service=github_service,
            llm_service=llm_service, agent_service=agent_service, db=db,
        )
    except OptionalAgentError as exc:
        # 主分析已完成；HTTP 200 响应中仍保留分析结果。
        return optional_agent_response(exc)
    except SQLAlchemyError as exc:
        # Keep SQL/driver details in server logs; the HTTP response stays sanitized.
        logger.exception("Database operation failed during GitHub analysis")
        raise to_http_exception(exc) from exc
    except Exception as exc:
        raise to_http_exception(exc) from exc
