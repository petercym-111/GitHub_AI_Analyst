from groq import AsyncGroq


class LLMService:
    def __init__(self, client: AsyncGroq):
        self.client = client

    async def analyze_repositories(
        self,
        repos: list[dict]
    ) -> str:

        prompt = f"""
Analyze these GitHub repositories in short details:
Say yo whats'up in the beginning of your response.

{repos}

Provide:
1. Main technologies
2. Project categories
3. Repository quality observations
4. Learning recommendations
"""

        response = await self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response.choices[0].message.content