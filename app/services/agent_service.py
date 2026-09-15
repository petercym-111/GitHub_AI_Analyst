"""Bounded Responses API orchestration, separate from GitHub analysis prompts."""

from dataclasses import dataclass
import json

from app.clients.groq_client import groq_client
from app.prompts.agent import SYSTEM_PROMPT
from app.services.LLM_services import LLMService
from app.services.tool_executor import ToolExecutor
from app.services.tools.tool_schemas import TOOLS


class EmptyModelResponseError(Exception):
    pass


class AgentLoopLimitError(Exception):
    pass


@dataclass
class ToolContext:
    """A result already fetched by the endpoint; never accepted from the HTTP body."""

    tool_name: str
    arguments: dict
    result: dict | list


class AgentService:
    # Profile -> repos -> analysis -> weather -> Word -> answer may need 6 turns.
    MAX_ITERATIONS = 8

    def __init__(self, tool_executor: ToolExecutor, *, client=None):
        self.tool_executor = tool_executor
        self.client = client if client is not None else groq_client

    async def chat(self, user_message: str, *, context: ToolContext | None = None) -> str:
        self.tool_executor.registry.results.clear()
        self.tool_executor.registry.fixed_username = (
            context.arguments.get("username") if context is not None else None
        )
        input_items = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        if context is not None:
            # Seed the already-completed operation as a call/result pair. This is
            # the same original data Word exports, not an LLM-generated copy.
            call_id = "endpoint_result"
            self.tool_executor.registry.results[call_id] = {
                "tool_name": context.tool_name,
                "result": context.result,
            }
            input_items[0]["content"] += (
                "\nThe server already completed the operation shown below. "
                "Use its result as the current endpoint data. For Word export, "
                "use source_call_ids=['endpoint_result']. Do not repeat that "
                "query or analysis unless the user explicitly asks to refresh it."
                "\nThe request body's username is fixed: "
                + json.dumps(context.arguments.get("username"))
                + ". All GitHub lookups must use this username, even if the message "
                "names another account or says 'my'. Never call get_github_me in "
                "this context. Do not ask the user to repeat their username. "
                "Weather questions need no GitHub lookup. When exporting this "
                "endpoint's result together with weather, include both "
                "'endpoint_result' and the weather call ID in source_call_ids."
            )
            input_items.extend([
                {
                    "type": "function_call",
                    "name": context.tool_name,
                    "call_id": call_id,
                    "arguments": json.dumps(context.arguments, ensure_ascii=False),
                },
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(context.result, ensure_ascii=False),
                },
            ])
        for _ in range(self.MAX_ITERATIONS):
            response = await self.client.responses.create(
                model=LLMService.MODEL_NAME,
                input=input_items,
                tools=TOOLS,
            )
            # Preserve ALL outputs (including reasoning), then append call results.
            input_items.extend(
                item.model_dump(mode="json", exclude_none=True)
                for item in response.output
            )
            tool_calls = [item for item in response.output if item.type == "function_call"]
            if tool_calls:
                # Sequential execution avoids sharing a SQLAlchemy session concurrently.
                for tool_call in tool_calls:
                    input_items.append(await self.tool_executor.execute(tool_call))
                continue

            answer = response.output_text
            if not answer or not answer.strip():
                raise EmptyModelResponseError("Model returned no tool call and no final answer.")
            return answer

        raise AgentLoopLimitError(
            f"Agent exceeded the maximum number of iterations ({self.MAX_ITERATIONS})."
        )
