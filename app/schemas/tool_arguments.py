"""Validate model-generated arguments on the server, even with strict schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.endpoint_instruction import GitHubUsername


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WeatherArguments(ToolArguments):
    location: str = Field(min_length=1)
    units: Literal["celsius", "fahrenheit"]


class WordDocArguments(ToolArguments):
    content: str
    filename: str = Field(min_length=1)
    # None preserves the original content + filename calling convention.
    source_call_ids: list[str] | None = None


class MeArguments(ToolArguments):
    pass


class AnalysisArguments(ToolArguments):
    username: GitHubUsername


class ReposArguments(AnalysisArguments):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=30, ge=1, le=100)


TOOL_ARGUMENT_MODELS = {
    "get_weather": WeatherArguments,
    "get_word_doc": WordDocArguments,
    "get_github_me": MeArguments,
    "get_github_repos": ReposArguments,
    "get_github_analysis": AnalysisArguments,
}
