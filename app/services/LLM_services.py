import json

from groq import AsyncGroq
from app.configurations.config import settings

from app.prompts.github_analysis import (
    SYSTEM_PROMPT,
    USER_PROMPT,
)

#from app.schemas.github_analysis import GitHubAnalysisSchema

# Calling the Groq LLM by Groq API key
def get_llm_service():
    client = AsyncGroq(
        api_key=settings.GROQ_API_KEY
    )
    return LLMService(client)

class LLMService:

    MODEL_NAME = "llama-3.3-70b-versatile" # 以后改模型只需要改这里

    def __init__(self,client: AsyncGroq):
        self.client = client # AsyncGroq 已经包含了API Key， 因此 llm_service.py 不需要再次创建 AsyncGroq。

    @staticmethod # 这里并没有使用class（LLMService）的任何东西，只是设计上它算是在LLMService里面。但可以读取到class state（MODEL_NAME），不过不应依赖class state。如果这里需要经常读取或修改class state，那么它更适合设计成 ”@classmethod“
    def _summarize_repositories( # 这里还没有动用到LLM，这里只是在从原始的 GitHub JSON 里挑出最有价值的几个字段，再组成新的 JSON
        repos: list[dict],
    ) -> list[dict]:

        summary = []

        for repo in repos: # 数据筛选
            summary.append(
                {
                    "name": repo.get(
                        "name"
                    ),
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
    ) :

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
                model=self.MODEL_NAME,
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

        content = response.choices[0].message.content

        #print(f"!!!!!!here is content!!!!!"+content+"!!!!!!!!!")

        data = json.loads(content)

        return data
