from app.schemas.tool_arguments import AnalysisArguments, MeArguments, ReposArguments


def _tool(name, description, argument_model):
    parameters = argument_model.model_json_schema()
    # Responses strict mode requires every property to appear in required.
    # Runtime defaults remain useful when these handlers are called in Python.
    parameters["required"] = list(parameters["properties"])
    for value in parameters["properties"].values():
        value.pop("default", None)
    return {
        "type": "function", "name": name, "description": description,
        "parameters": parameters, "strict": True,
    }


get_github_me_tool = _tool(
    "get_github_me",
    "Get the configured GitHub token owner's profile, identical to GET /github/me. "
    "Use for 'me' or 'my GitHub profile'; it is not the chat caller's identity.",
    MeArguments,
)
get_github_repos_tool = _tool(
    "get_github_repos",
    "Get one page of a user's public repositories, the repositories data from "
    "POST /github/users/repos. Use the fixed endpoint username when provided. "
    "Use page=1 and per_page=30 by default. "
    "This is one page, not necessarily all repositories.",
    ReposArguments,
)
get_github_analysis_tool = _tool(
    "get_github_analysis",
    "Get repository analysis, the core result of POST /github/users/analysis. "
    "Use the fixed endpoint username when provided. "
    "Reuses cached analysis if present; otherwise analyzes the first 30 repositories "
    "and saves analysis and request logs. Returns username, cached, and analysis.",
    AnalysisArguments,
)
