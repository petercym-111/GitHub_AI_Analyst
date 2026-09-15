from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# Validate the fixed lookup identity separately from optional natural language.
GitHubUsername = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=1, max_length=39,
        pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
    ),
]
InstructionText = Annotated[str, StringConstraints(strict=True, max_length=10000)]


class EndpointInstruction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"username": "octocat", "message": ""}]},
    )

    username: GitHubUsername = Field(
        description="必填：要查询的 GitHub 用户名。GitHub API 会进一步确认用户是否存在。",
    )

    message: InstructionText = Field(
        default="",
        description="可选：询问天气或要求导出 Word，无须重复用户名。留空只返回本接口的仓库或分析数据。",
    )


class AgentError(BaseModel):
    code: str
    message: str
