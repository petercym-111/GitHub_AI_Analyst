from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.exceptions import OptionalAgentError
from app.routes.error_handlers import optional_agent_response, to_http_exception
from app.services.agent_service import AgentService
from app.services.github_services import GitHubService, get_github_service
from app.services.github_workflow_service import get_analysis
from app.services.llm_service import LLMService

router = APIRouter(tags=["LLM Analysis"])


@router.post("/users/{username}/analysis")
async def analyze_user_repositories(
    username: str,
    message: str | None = Query(default=None, max_length=4000),
    github_service: GitHubService = Depends(get_github_service),
    llm_service: LLMService = Depends(LLMService),
    agent_service: AgentService = Depends(AgentService),
    db: Session = Depends(get_db),
):
    # Endpoint owns HTTP input/output; the service owns the workflow.
    try:
        return await get_analysis(
            username=username, message=message, github_service=github_service,
            llm_service=llm_service, agent_service=agent_service, db=db,
        )
    except OptionalAgentError as exc:
        return optional_agent_response(exc)
    except Exception as exc:
        raise to_http_exception(exc) from exc
