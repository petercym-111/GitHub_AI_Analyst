from app.crud.github_analysis import GitHubAnalysisCRUD
from app.crud.analysis_request_log import AnalysisRequestLogCRUD

from app.database.dependencies import get_db

from app.services.github_services import GitHubService
from app.services.github_services import get_github_service
from app.services.LLM_services import LLMService
from app.services.LLM_services import get_llm_service

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
import time

router = APIRouter(tags=["LLM Analysis"])

@router.post("/users/{username}/analysis")
async def analyze_user_repositories(
    username: str,
    github_service: GitHubService = Depends(
        get_github_service
    ),
    llm_service: LLMService = Depends(
        get_llm_service
    ),
    db: Session = Depends(get_db),
):
    start = time.perf_counter() # 记录request开始时间。给予后面的“duration_ms = ...” 用来分析耗时

    try:
        # check cache
        cached = (
            await GitHubAnalysisCRUD.get_by_username( # 先查数据库：这个 GitHub 用户以前分析过了吗？
                db,
                username,
            )
        )

        if cached: # 如果这个用户存在于database，下面的return直接返回用户的分析结果，不需要重新回去Github， 也不需要找这个用户再丢给LLM分析。
            duration = int(
                (time.perf_counter() - start)
                * 1000
            )

            await AnalysisRequestLogCRUD.create(
                db,
                github_username=username,
                analysis_id=cached.id, # access the variable "cached" that which return back the data from database
                success=True,
                duration_ms=duration,
            )

            return { # 这个return返回保存过的用户名和分析结果
                "username": username,
                "cached": True,
                "analysis": cached.analysis,
            }

        # fetch repositories
        repos = await github_service.get_user_repos( # 调用 GitHub API，获取 repositories。
            username=username,
            per_page=30,
        )

        # llm analysis
        analysis = (
            await llm_service.analyze_repositories( # 把 repos 丢给 LLM。LLM就可以分析了
                repos,
            )
        )

        # save analysis 保存分析结果
        saved_analysis = (
            await GitHubAnalysisCRUD.create(
                db,
                github_username=username,
                repo_snapshot=repos,
                analysis=analysis,
                model_name=llm_service.MODEL_NAME,
            )
        )

        duration = int(
            (time.perf_counter() - start)
            * 1000
        )

        # save request log 保存request日志，例如：什么时候请求，成功失败，耗时多少
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

        # 如果上面的exception抓到其中一个：GitHub 挂了，LLM 挂了。
        await AnalysisRequestLogCRUD.create( # 这里仍然会记录/保存失败日志。然后在下面的raise error返回500。除了Database 挂了的话，就保存不到数据进去database。
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
# GitHubAnalysisCRUD.get_by_username() （Check Cache）
#     ↓
# Cache Hit?
#   /     \
#  yes    no
#   |      |
# return   GitHubService（GitHub API）
#          ↓
#          LLMService
#          ↓
#          GitHubAnalysisCRUD.create() （Save Analysis）
#          ↓
#          AnalysisRequestLogCRUD.create() （Save Log）
#          ↓
#          return