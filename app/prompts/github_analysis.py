# prompts for LLM_services.py
# 拆成两个 Prompt，以后只改 Prompt，不需要改 Python 代码。

SYSTEM_PROMPT = """
You are a senior software architect.

Your task is to analyze GitHub repositories.

Rules:

- Only use the provided repository information.
- Do not invent technologies or projects.
- Keep observations concise.
- Return ONLY valid JSON.
"""

USER_PROMPT = """
Repositories:

{repositories}

Return exactly this JSON structure:

{{
    "overall_profile": "...",
    "main_technologies": [
        "..."
    ],
    "project_categories": [
        "..."
    ],
    "repository_quality": [
        "..."
    ],
    "learning_recommendations": [
        "..."
    ]
}}
"""