import asyncio
import json

import httpx
from pydantic import ValidationError

from app.exceptions import (
    ToolArgumentError, ToolExecutionError, ToolTimeoutError, UnknownToolError,
)
from app.services.tool_registry import TOOL_REGISTRY


class ToolExecutor:
    async def execute(self, tool_call) -> dict:
        tool = TOOL_REGISTRY.get(tool_call.name)
        if tool is None:
            raise UnknownToolError(f"Unknown tool: {tool_call.name}")
        try:
            arguments = tool.arguments.model_validate_json(tool_call.arguments).model_dump()
        except ValidationError as exc:
            raise ToolArgumentError("Invalid tool arguments") from exc

        try:
            result = await asyncio.wait_for(tool.handler(**arguments), timeout=tool.timeout)
            output = json.dumps(result, ensure_ascii=False)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ToolTimeoutError("Tool timed out") from exc
        except Exception as exc:
            raise ToolExecutionError("Tool execution failed") from exc

        return {
            "type": "function_call_output",
            "call_id": tool_call.call_id,
            "output": output,
        }
