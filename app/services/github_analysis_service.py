import hashlib
import json

from pydantic import ValidationError

from app.exceptions import InvalidModelResponseError

from app.prompts.github_analysis import SYSTEM_PROMPT, USER_PROMPT
from app.schemas.github_analysis import GitHubAnalysisSchema
from app.services.llm_service import LLMService


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

    try:
        analysis = GitHubAnalysisSchema.model_validate_json(content)
    except ValidationError as exc:
        raise InvalidModelResponseError("Analysis does not match its schema") from exc
    return analysis.model_dump()


def get_analysis_version(model_name: str) -> str:
    """Invalidate cached analyses when the model, prompt, or input scope changes."""
    version_source = "\n".join((model_name, SYSTEM_PROMPT, USER_PROMPT, "repos:first-page:30"))
    return hashlib.sha256(version_source.encode("utf-8")).hexdigest() # SHA-256 是 256 位，也就是 64 个十六进制字符,十六进制哈希值
    # 程序把 model_name、prompt 和输入范围组合成一个固定长度的指纹，保存并比较它。
    # 这样数据库查询只需比较一个短字段例如“6473da0dbd20be386449792b58724bc8b2f6d0232b074e94b8315190c4d3a449”，
    # 就能判断当前配置是否与生成缓存时一致；不用保存整份配置来做匹配。
