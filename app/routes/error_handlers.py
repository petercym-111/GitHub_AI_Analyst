"""Shared HTTP error translation, imported by both GitHub endpoints."""
import httpx
from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import (
    AgentLoopLimitError, EmptyModelResponseError, InvalidModelResponseError,
    OptionalAgentError, ToolArgumentError, ToolExecutionError,
    ToolTimeoutError, UnknownToolError,
)


# Specific SDK subclasses must precede their parent classes.
ERROR_RESPONSES = {
    UnknownToolError: (502, "UNKNOWN_TOOL", "The AI model requested an unavailable tool."),
    ToolArgumentError: (502, "TOOL_ARGUMENT_ERROR", "The AI model provided invalid tool arguments."),
    ToolTimeoutError: (504, "TOOL_TIMEOUT", "A required operation timed out."),
    ToolExecutionError: (500, "TOOL_EXECUTION_ERROR", "Tool execution failed."),
    EmptyModelResponseError: (502, "EMPTY_MODEL_RESPONSE", "The AI model returned an empty response."),
    InvalidModelResponseError: (502, "INVALID_MODEL_RESPONSE", "The AI model returned invalid analysis data."),
    AgentLoopLimitError: (500, "AGENT_LOOP_LIMIT", "The AI agent exceeded its execution limit."),
    APITimeoutError: (504, "MODEL_TIMEOUT", "The AI service timed out."),
    RateLimitError: (503, "MODEL_RATE_LIMIT", "The AI service is temporarily rate limited."),
    APIConnectionError: (502, "MODEL_CONNECTION_ERROR", "Could not connect to the AI service."),
    APIStatusError: (502, "MODEL_API_ERROR", "The AI service could not process the request."),
    httpx.TimeoutException: (504, "GITHUB_TIMEOUT", "GitHub timed out."),
    httpx.RequestError: (502, "GITHUB_CONNECTION_ERROR", "Could not connect to GitHub."),
    SQLAlchemyError: (500, "DATABASE_ERROR", "The database operation failed."),
}


def to_http_exception(error: Exception) -> HTTPException:
    if isinstance(error, httpx.HTTPStatusError):
        return HTTPException(
            status_code=error.response.status_code,
            detail={"code": "GITHUB_API_ERROR", "message": "GitHub API error"},
        )
    for error_type, (status, code, message) in ERROR_RESPONSES.items():
        if isinstance(error, error_type):
            return HTTPException(status_code=status, detail={"code": code, "message": message})
    return HTTPException(
        status_code=500,
        detail={"code": "INTERNAL_ERROR", "message": "The request could not be completed."},
    )


def optional_agent_response(error: OptionalAgentError) -> dict:
    # Core work succeeded: keep HTTP 200 and expose the specific optional error.
    detail = to_http_exception(error.cause).detail
    if detail["code"] == "INTERNAL_ERROR":
        detail = {"code": "AGENT_EXECUTION_ERROR", "message": "Additional task failed."}
    return {**error.endpoint_result, "agent_error": detail}
