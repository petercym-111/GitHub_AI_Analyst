from fastapi import APIRouter, Depends, HTTPException, Query
# APIRouter → modular route grouping
# HTTPException → controlled API errors
# Query → query validation (pagination rules)
import httpx # In this file that used only for exception type handling

from app.services.github_services import GitHubService
from app.services.github_services import get_github_service
from app.services.agent_service import AgentService
from app.services.github_workflow_service import get_repositories
from app.exceptions import OptionalAgentError
from app.routes.error_handlers import optional_agent_response, to_http_exception

# This is a 3-layer dependency pipeline:
# HTTP Client → GitHubService → API Routes
# -----------------------------------------------
# app.state.http_client
#         ↓ (Depends)
# get_http_client
#         ↓
# GitHubService
#         ↓
# endpoint (/me, /repos)

router = APIRouter(tags=["Get Me and Get Repos"]) # creates isolated route module, later attached in main.py

@router.get("/me") # Attached later via include_router in main.py
async def get_me( # 这里还不涉及任何LLM， 只有单纯的github service
    service: GitHubService = Depends(get_github_service) # 为什么这里需要“GitHubService”，即使有或没有都可以运行
                                                         # 因为我或者别人可以立刻知道这个variable（service）是一个 “GitHubService” 的instance，可以调用它的methods和attributes。不需要跳去“get_github_service”才能猜出类型（Type Hint）
):
    try:
        return await service.get_user()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "message": "GitHub API error",
                "status": e.response.status_code
            }
        )

@router.post("/users/{username}/repos")
async def get_repos(
    username: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(1, ge=1, le=1),
    message: str | None = Query(default=None, max_length=4000),
    agent_service: AgentService = Depends(AgentService),
    service: GitHubService = Depends(get_github_service),
):
    try:
        return await get_repositories(
            username=username, page=page, per_page=per_page, message=message,
            github_service=service, agent_service=agent_service,
        )
    except OptionalAgentError as exc:
        return optional_agent_response(exc)
    except Exception as exc:
        raise to_http_exception(exc) from exc
