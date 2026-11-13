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
        # 1. 只从服务器端 allowlist 查找模型请求的工具名称。
        tool = TOOL_REGISTRY.get(tool_call.name)
        if tool is None:
            raise UnknownToolError(f"Unknown tool: {tool_call.name}")
        try:
            # 2. dispatch 前使用该工具注册的 Pydantic model 校验 JSON 参数。
            arguments = tool.arguments.model_validate_json(tool_call.arguments).model_dump()
        except ValidationError as exc:
            raise ToolArgumentError("Invalid tool arguments") from exc

        try:
            # 3. 只执行已注册的 handler，按工具策略控制 timeout，并序列化结果。
            result = await asyncio.wait_for(tool.handler(**arguments), timeout=tool.timeout)
            output = json.dumps(result, ensure_ascii=False)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ToolTimeoutError("Tool timed out") from exc
        except Exception as exc:
            raise ToolExecutionError("Tool execution failed") from exc

        # 4. Responses API 的工具结果必须关联发起该调用的 function call_id。
        return {
            "type": "function_call_output",
            "call_id": tool_call.call_id,
            "output": output,
        }
