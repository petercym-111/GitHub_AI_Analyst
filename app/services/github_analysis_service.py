import json

from app.prompts.github_analysis import SYSTEM_PROMPT, USER_PROMPT
from app.schemas.github_analysis import GitHubAnalysisSchema
from app.services.LLM_services import LLMService


def _summarize_repositories(repos: list[dict]) -> list[dict]:
    # 模块内部的纯函数：筛选 GitHub 字段，不调用 LLM，也不修改原始数据。
    summary = []

    for repo in repos:
        summary.append(
            {
                "name": repo.get("name"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "topics": repo.get("topics"),
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
            }
        )

    return summary


async def analyze_repositories(
    repos: list[dict],
    llm_service: LLMService,
) -> dict:
    # 分析流程：筛选字段 → 组装 GitHub prompt → 调用 LLM → 解析 JSON。
    # LLMService 由调用方传入，本模块不创建模型客户端。
    repo_summary = _summarize_repositories(repos)
    user_prompt = USER_PROMPT.format(
        repositories=json.dumps(repo_summary, indent=2),
    )

    content = await llm_service.generate_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Validate the model's JSON shape before it can be persisted or exported.
    return GitHubAnalysisSchema.model_validate_json(content).model_dump()
