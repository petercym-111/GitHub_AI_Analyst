from app.services.tools.github_tools import (
    get_github_analysis_tool,
    get_github_me_tool,
    get_github_repos_tool,
)
from app.services.tools.weather_tool import get_weather_tool
from app.services.tools.word_doc_tool import get_word_doc_tool

TOOLS = [
    get_weather_tool,
    get_word_doc_tool,
    get_github_me_tool,
    get_github_repos_tool,
    get_github_analysis_tool,
]
