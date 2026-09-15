from typing import Any

from pydantic import BaseModel

from app.schemas.endpoint_instruction import AgentError


class RepositoryAgentResponse(BaseModel):
    username: str
    page: int
    per_page: int
    # Retain ALL fields from GitHub's repository objects.
    repositories: list[dict[str, Any]]
    answer: str | None = None
    agent_error: AgentError | None = None
