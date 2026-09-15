from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.services.agent_service import AgentService
from app.services.github_services import GitHubService, get_github_service
from app.services.LLM_services import LLMService
from app.services.tool_executor import ToolExecutor
from app.services.tool_registry import ToolRegistry


def get_agent_service(
    github_service: GitHubService = Depends(get_github_service),
    llm_service: LLMService = Depends(LLMService),
    db: Session = Depends(get_db),
) -> AgentService:
    # Request-scoped wiring; the HTTP and model clients still reuse connections.
    registry = ToolRegistry(github_service, llm_service, db)
    return AgentService(ToolExecutor(registry), client=llm_service.client)
