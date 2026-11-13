from pydantic import BaseModel, ConfigDict


class GitHubAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_profile: str
    main_technologies: list[str]
    project_categories: list[str]
    repository_quality: list[str]
    learning_recommendations: list[str]
