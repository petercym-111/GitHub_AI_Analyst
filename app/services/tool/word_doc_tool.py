# 给 LLM 的工具定义；支持仓库资料、分析结果和天气，不限制为天气文档。
create_doc_word_tool = {
    "type": "function",
    "name": "create_doc_word",
    "description": (
        "Creates a Microsoft Word (.docx) document containing the supplied text. "
        "Use only when the user explicitly asks to create, save, or export a Word document,"
        "reject user if the user ask to create a word document without specify "
        "what type of content should be in the document."
        "The document may contain repository data, completed "
        "GitHub analysis, weather results, or a requested combination. "
        "Use endpoint_result as the source for repository data and analysis, "
        "including cached analysis. Preserve the supplied facts and pagination "
        "scope; do not invent missing repositories or analysis. "
        "When weather is requested, call get_weather first and use its result. "
        "Do not require weather for an analysis-only or repository-only export. "
        "Report file creation success only after this tool succeeds, and use "
        "the filename and path returned by the tool."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "The complete text to write, in the user's requested language. "
                    "Include the requested source data or analysis, not a promise "
                    "to add it later. Use plain-text headings and newlines; this "
                    "tool writes text and does not render Markdown formatting. "
                    "Include weather only when requested and retrieved."
                ),
            },
            "filename": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "A descriptive plain filename ending in .docx, for example "
                    "github_analysis.docx. Do not include directory paths or "
                    "Windows filename characters such as < > : \" / | ? *. "
                    "The server adds a unique prefix to avoid overwriting files."
                ),
            },
        },
        "required": ["content", "filename"],
        "additionalProperties": False,
    },
    "strict": True,
}
