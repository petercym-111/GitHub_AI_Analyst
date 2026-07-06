import json

from groq import AsyncGroq

from app.prompts.github_analysis import (
    SYSTEM_PROMPT,
    USER_PROMPT,
)

from app.schemas.github_analysis import (
    GitHubAnalysisSchema,
)


class LLMService:

    def __init__(
        self,
        client: AsyncGroq,
    ):
        self.client = client

    @staticmethod
    def _summarize_repositories(
        repos: list[dict],
    ) -> list[dict]:

        summary = []

        for repo in repos:
            summary.append(
                {
                    "name": repo.get("name"),
                    "description": repo.get(
                        "description"
                    ),
                    "language": repo.get(
                        "language"
                    ),
                    "topics": repo.get(
                        "topics"
                    ),
                    "stars": repo.get(
                        "stargazers_count"
                    ),
                    "forks": repo.get(
                        "forks_count"
                    ),
                }
            )

        return summary

    async def analyze_repositories(
        self,
        repos: list[dict],
    ) -> GitHubAnalysisSchema:

        repo_summary = self._summarize_repositories(
            repos
        )

        user_prompt = USER_PROMPT.format(
            repositories=json.dumps(
                repo_summary,
                indent=2,
            )
        )

        response = (
            await self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_format={
                    "type": "json_object"
                },
            )
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        data = json.loads(content)

        return GitHubAnalysisSchema.model_validate(
            data
        )