from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.clients.weather_client import WeatherClient
from app.clients.word_doc_client import WordClient
from app.services.tool.weather_tool import get_weather_tool
from app.services.tool.word_doc_tool import create_doc_word_tool


# Server-side validation remains necessary even when the model uses strict tools.
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    location: str = Field(min_length=1)
    units: Literal["celsius", "fahrenheit"]


class WordArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content: str = Field(min_length=1)
    filename: str = Field(min_length=1)


async def get_weather(location: str, units: str) -> dict:
    return await WeatherClient().get_weather(location=location, units=units)


async def create_doc_word(content: str, filename: str) -> dict:
    return await WordClient().create_document(content=content, filename=filename)


@dataclass(frozen=True)
class ToolDefinition:
    handler: Callable[..., Awaitable[dict]]
    arguments: type[BaseModel]
    description: str
    timeout: float | None = 10
    returns_document: bool = False


# Read names from the advertised schemas; dispatch is still an explicit allowlist.
TOOL_REGISTRY = {
    get_weather_tool["name"]: ToolDefinition(
        handler=get_weather,
        arguments=WeatherArguments,
        description=get_weather_tool["description"],
    ),
    create_doc_word_tool["name"]: ToolDefinition(
        handler=create_doc_word,
        arguments=WordArguments,
        description=create_doc_word_tool["description"],
        # Cancelling an await cannot stop the document-writing worker thread.
        timeout=None,
        returns_document=True,
    ),
}
