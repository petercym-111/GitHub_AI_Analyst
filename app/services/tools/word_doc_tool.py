get_word_doc_tool = {
    "type": "function",
    "name": "get_word_doc",
    "description": (
        "Create a Microsoft Word document only when the user asks to create, save, "
        "or export one. Supports weather and the outputs of GET /github/me, "
        "GET /github/users/{username}/repos, and POST /github/users/{username}/analysis. "
        "Fetch requested data first, then pass those calls' call_id values in "
        "source_call_ids: the server writes the original results without retyping. "
        "Multiple results may be combined in one document. Use content for an optional "
        "heading or explanation. For data already supplied by the user, put its complete "
        "content in content and set source_call_ids to null. Do not invent data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Document text or heading; may be empty when using source_call_ids.",
            },
            "filename": {
                "type": "string",
                "description": "Word filename ending in .docx, without a directory.",
            },
            "source_call_ids": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "call_id values of completed weather/GitHub calls in this request, or null.",
            },
        },
        "required": ["content", "filename", "source_call_ids"],
        "additionalProperties": False,
    },
    "strict": True,
}
