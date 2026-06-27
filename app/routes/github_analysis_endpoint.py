from app.crud.github_analysis import GitHubAnalysisCRUD
from app.crud.analysis_request_log import AnalysisRequestLogCRUD
from app.database.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.routes.endpoints import *

import time

router = APIRouter(tags=["LLM Analysis"])

@router.get("/users/{username}/analysis")
async def analyze_user_repositories(
    username: str,
    github_service: GitHubService = Depends(
        get_github_service
    ),
    llm_service: LLMService = Depends(
        get_llm_service
    ),
    db: AsyncSession = Depends(get_db),
):
    start = time.perf_counter()

    try:
        # check cache
        cached = (
            await GitHubAnalysisCRUD.get_by_username(
                db,
                username,
            )
        )

        if cached:
            duration = int(
                (time.perf_counter() - start)
                * 1000
            )

            await AnalysisRequestLogCRUD.create(
                db,
                github_username=username,
                analysis_id=cached.id,
                success=True,
                duration_ms=duration,
            )

            return {
                "username": username,
                "cached": True,
                "analysis": cached.analysis,
            }

        # fetch repositories
        repos = await github_service.get_user_repos(
            username=username,
            per_page=30,
        )

        # llm analysis
        analysis = (
            await llm_service.analyze_repositories(
                repos
            )
        )

        # save analysis
        saved_analysis = (
            await GitHubAnalysisCRUD.create(
                db,
                github_username=username,
                repo_snapshot=repos,
                analysis=analysis,
                model_name="openai/gpt-oss-120b",
            )
        )

        duration = int(
            (time.perf_counter() - start)
            * 1000
        )

        # save request log
        await AnalysisRequestLogCRUD.create(
            db,
            github_username=username,
            analysis_id=saved_analysis.id,
            success=True,
            duration_ms=duration,
        )

        return {
            "username": username,
            "cached": False,
            "analysis": analysis,
        }

    except Exception as e:
        duration = int(
            (time.perf_counter() - start)
            * 1000
        )

        await AnalysisRequestLogCRUD.create(
            db,
            github_username=username,
            analysis_id=None,
            success=False,
            duration_ms=duration,
            error_message=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# - Workflow -

# Request
#     ↓
# Endpoint
#     ↓
# GitHubAnalysisCRUD.get_by_username()
#     ↓
# Cache Hit?
#   /     \
#  yes    no
#   |      |
# return   GitHubService
#          ↓
#          LLMService
#          ↓
#          GitHubAnalysisCRUD.create()
#          ↓
#          AnalysisRequestLogCRUD.create()
#          ↓
#          return