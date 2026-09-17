# 给 LLM 的工具定义；实际调用由 tool_registry 和 ToolExecutor 负责。
get_weather_tool = {
    "type": "function",
    "name": "get_weather",
    "description": (
        "Retrieves the current temperature for a specified city. "
        "Use this tool when the user asks about current weather; do not invent "
        "live weather data. This tool does not provide historical weather or "
        "multi-day forecasts. If the location is missing, ask the user for it. "
        "If a Word document must contain weather, retrieve the weather first "
        "and use the returned result when creating the document."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "The city to look up, preferably its full name, for example "
                    "Tokyo or Kuala Lumpur. Do not infer the weather location "
                    "from the GitHub username."
                ),
            },
            "units": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": (
                    "The temperature unit requested by the user. "
                    "Use celsius when no unit is specified."
                ),
            },
        },
        # strict 模式下，所有已声明参数都必须提供。
        "required": ["location", "units"],
        "additionalProperties": False,
    },
    # 请求提供方按 schema 生成参数；后端仍会再次校验。
    "strict": True,
}
