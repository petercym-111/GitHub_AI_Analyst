from pydantic import BaseModel


class GitHubAnalysisSchema(BaseModel):
    overall_profile: str
    main_technologies: list[str]
    project_categories: list[str]
    repository_quality: list[str]
    learning_recommendations: list[str]