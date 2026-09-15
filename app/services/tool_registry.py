"""Request-scoped allowlist: tool names map to explicitly wired Python methods."""

import json

from sqlalchemy.orm import Session

from app.clients.weather_client import WeatherClient
from app.clients.word_doc_client import WordClient
from app.services.github_analysis_workflow import get_or_create_analysis
from app.services.github_services import GitHubService
from app.services.LLM_services import LLMService


class ToolRegistry:
    def __init__(
        self,
        github_service: GitHubService,
        llm_service: LLMService,
        db: Session,
        *,
        weather_client: WeatherClient | None = None,
        word_client: WordClient | None = None,
    ):
        self.github_service = github_service
        self.llm_service = llm_service
        self.db = db
        self.weather_client = weather_client if weather_client is not None else WeatherClient()
        self.word_client = word_client if word_client is not None else WordClient()
        # Never global: one caller cannot reference another request's results.
        self.results: dict[str, dict] = {}
        self.fixed_username: str | None = None
        self.tools = {
            "get_weather": self.get_weather,
            "get_word_doc": self.get_word_doc,
            "get_github_me": self.get_github_me,
            "get_github_repos": self.get_github_repos,
            "get_github_analysis": self.get_github_analysis,
        }

    async def get_weather(self, location: str, units: str):
        return await self.weather_client.get_weather(location=location, units=units)

    async def get_github_me(self):
        if self.fixed_username is not None:
            raise ValueError("Use the endpoint username, not the configured token owner.")
        return await self.github_service.get_user()

    def _check_username(self, username: str):
        # Enforce this in Python: a prompt alone cannot lock a tool's arguments.
        if self.fixed_username is not None and username.lower() != self.fixed_username.lower():
            raise ValueError("GitHub tools must use the username from the request body.")

    async def get_github_repos(self, username: str, page: int = 1, per_page: int = 30):
        self._check_username(username)
        return await self.github_service.get_user_repos(username, page, per_page)

    async def get_github_analysis(self, username: str):
        self._check_username(username)
        return await get_or_create_analysis(
            username,
            github_service=self.github_service,
            llm_service=self.llm_service,
            db=self.db,
        )

    async def get_word_doc(
        self, content: str, filename: str, source_call_ids: list[str] | None = None,
    ):
        # Critical boundary: Python copies exact source data; the LLM selects it.
        sections = [content] if content.strip() else []
        for call_id in source_call_ids or []:
            source = self.results.get(call_id)
            if source is None or source["tool_name"] == "get_word_doc":
                raise ValueError("Document source must be a completed weather or GitHub call.")
            sections.append(
                f"{source['tool_name']}\n"
                + json.dumps(source["result"], ensure_ascii=False, indent=2)
            )
        return await self.word_client.create_document(
            content="\n\n".join(sections), filename=filename,
        )
