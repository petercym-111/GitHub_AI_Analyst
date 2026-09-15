from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.configurations.agent import get_agent_service
from app.routes.agent_response import run_agent
from app.schemas.endpoint_instruction import EndpointInstruction
from app.schemas.github_analysis import GitHubAnalysisResponse
from app.services.agent_service import AgentService, ToolContext
from app.services.github_analysis_workflow import get_or_create_analysis
from app.services.github_services import GitHubService, get_github_service
from app.services.LLM_services import LLMService

router = APIRouter(tags=["LLM Analysis"])


@router.post(
    "/users/analysis",
    response_model=GitHubAnalysisResponse,
    response_model_exclude_unset=True,
)
async def analyze_user_repositories(
    instruction: EndpointInstruction,
    github_service: GitHubService = Depends(get_github_service),
    llm_service: LLMService = Depends(LLMService),
    db: Session = Depends(get_db),
    agent_service: AgentService = Depends(get_agent_service),
):
    username = instruction.username
    # HTTP adapter only. Agent tools reuse the same cache/persistence workflow.
    try:
        # A cached analysis does not prove that the GitHub account still exists.
        await github_service.get_public_user(username)
        result = await get_or_create_analysis(
            username, github_service=github_service, llm_service=llm_service, db=db,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={"message": "GitHub API error", "status": exc.response.status_code},
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="GitHub API timed out") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to GitHub") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Process instructions against this exact result, including its cached flag.
    agent_result = await run_agent(
        agent_service,
        instruction.message,
        context=ToolContext(
            tool_name="get_github_analysis",
            arguments={"username": username},
            result=result,
        ),
    )
    return {**result, **agent_result}
