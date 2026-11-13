from app.services.tool.weather_tool import get_weather_tool
from app.services.tool.word_doc_tool import create_doc_word_tool


# 汇总提供给 Responses API 的工具定义，不执行工具。
TOOLS = [
    get_weather_tool,
    create_doc_word_tool,
]
