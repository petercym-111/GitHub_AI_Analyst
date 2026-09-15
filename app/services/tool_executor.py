import asyncio
import json
import logging

import httpx
from openai import APIError
from pydantic import ValidationError

from app.schemas.tool_arguments import TOOL_ARGUMENT_MODELS
from app.services.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolArgumentError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


class UnknownToolError(Exception):
    pass


class ToolTimeoutError(Exception):
    pass


class ToolExecutor:
    TOOL_TIMEOUT = 10
    # Analysis includes a nested LLM request, so it needs its own time budget.
    ANALYSIS_TIMEOUT = 120

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(self, tool_call) -> dict:
        tool_name = tool_call.name
        handler = self.registry.tools.get(tool_name)
        if handler is None:
            raise UnknownToolError(f"Unknown tool: {tool_name}")

        try:
            arguments = TOOL_ARGUMENT_MODELS[tool_name].model_validate_json(
                tool_call.arguments,
            ).model_dump()
        except ValidationError as exc:
            raise ToolArgumentError(f"Invalid arguments for tool '{tool_name}'.") from exc

        timeout = self.ANALYSIS_TIMEOUT if tool_name == "get_github_analysis" else self.TOOL_TIMEOUT
        try:
            result = await asyncio.wait_for(handler(**arguments), timeout=timeout)
            output = json.dumps(result, ensure_ascii=False)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ToolTimeoutError(f"Tool '{tool_name}' timed out.") from exc
        except APIError:
            # Preserve the existing model error contract for nested analysis calls.
            raise
        except ValueError as exc:
            if tool_name == "get_word_doc":
                raise ToolArgumentError("Invalid document arguments.") from exc
            raise ToolExecutionError("Tool execution failed.") from exc
        except Exception as exc:
            logger.exception("Unexpected error while executing tool '%s'", tool_name)
            raise ToolExecutionError("Tool execution failed.") from exc

        self.registry.results[tool_call.call_id] = {"tool_name": tool_name, "result": result}
        return {
            "type": "function_call_output",
            "call_id": tool_call.call_id,
            "output": output,
        }
