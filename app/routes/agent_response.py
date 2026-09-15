"""Optional Agent errors must never replace a completed endpoint result."""

import logging

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from app.services.agent_service import (
    AgentService, ToolContext, EmptyModelResponseError, AgentLoopLimitError,
)
from app.services.tool_executor import (
    UnknownToolError, ToolTimeoutError, ToolExecutionError, ToolArgumentError,
)


logger = logging.getLogger(__name__)


async def run_agent(
    service: AgentService, message: str, *, context: ToolContext,
) -> dict:
    if not message.strip():
        return {}
    try:
        return {"answer": await _run_agent(service, message, context=context)}
    except HTTPException as exc:
        return {"agent_error": exc.detail}
    except Exception:
        logger.exception("Optional Agent instruction failed after endpoint completed")
        return {"agent_error": {
            "code": "AGENT_EXECUTION_ERROR", "message": "The optional instruction failed.",
        }}


async def _run_agent(
    service: AgentService, message: str, *, context: ToolContext,
) -> str:
    try:
        return await service.chat(message, context=context)

    # Translate execution failures into one deterministic public error contract.
    except UnknownToolError as e:

        raise HTTPException(
            status_code=502,
            detail={
                "code": "UNKNOWN_TOOL",
                "message": "The AI model requested an unavailable tool.",
            },
        ) from e

    except ToolArgumentError as e:

        raise HTTPException(
            status_code=502,
            detail={
                "code": "TOOL_ARGUMENT_ERROR",
                "message": "The AI model provided invalid tool arguments.",
            },
        ) from e

    except ToolTimeoutError as e:

        raise HTTPException(
            status_code=504,
            detail={
                "code": "TOOL_TIMEOUT",
                "message": "A required operation timed out.",
            },
        ) from e

    except ToolExecutionError as e:

        raise HTTPException(
            status_code=500,
            detail={
                "code": "TOOL_EXECUTION_ERROR",
                "message": "Tool execution failed.",
            },
        ) from e

    except EmptyModelResponseError as e:

        raise HTTPException(
            status_code=502,
            detail={
                "code": "EMPTY_MODEL_RESPONSE",
                "message": (
                    "The AI model did not return a valid response."
                ),
            },
        ) from e

    except AgentLoopLimitError as e:

        raise HTTPException(
            status_code=500,
            detail={
                "code": "AGENT_LOOP_LIMIT",
                "message": (
                    "The AI agent could not complete the "
                    "request within the allowed execution limit."
                ),
            },
        ) from e

    # Catch specific SDK exceptions before their parent exception classes.
    except APITimeoutError as e:

        raise HTTPException(
            status_code=504,
            detail={
                "code": "MODEL_TIMEOUT",
                "message": "The AI service timed out.",
            },
        ) from e

    except RateLimitError as e:

        raise HTTPException(
            status_code=503,
            detail={
                "code": "MODEL_RATE_LIMIT",
                "message": "The AI service is temporarily unavailable due to rate limits.",
            },
        ) from e

    except APIConnectionError as e:

        raise HTTPException(
            status_code=502,
            detail={
                "code": "MODEL_CONNECTION_ERROR",
                "message": "Could not connect to the AI service.",
            },
        ) from e

    except APIStatusError as e:

        raise HTTPException(
            status_code=502,
            detail={
                "code": "MODEL_API_ERROR",
                "message": "The AI service could not process the request.",
            },
        ) from e
