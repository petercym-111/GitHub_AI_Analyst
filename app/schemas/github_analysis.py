from pydantic import BaseModel, ConfigDict

from app.schemas.endpoint_instruction import AgentError


class GitHubAnalysisSchema(BaseModel):
    # Enforce the known field types without dropping additional analysis data.
    model_config = ConfigDict(strict=True, extra="allow")

    overall_profile: str
    main_technologies: list[str]
    project_categories: list[str]
    repository_quality: list[str]
    learning_recommendations: list[str]


class GitHubAnalysisResponse(BaseModel):
    username: str
    cached: bool
    analysis: GitHubAnalysisSchema
    answer: str | None = None
    agent_error: AgentError | None = None
