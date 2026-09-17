import json

from app.clients.groq_client import groq_client
from app.prompts.agent import SYSTEM_PROMPT
from app.services.tool_executor import ToolExecutor
from app.services.tool.tool_schemas import TOOLS
from app.services.tool_registry import TOOL_REGISTRY
from app.exceptions import AgentLoopLimitError, EmptyModelResponseError

class AgentService:
    MODEL_NAME = "openai/gpt-oss-120b"
    MAX_ITERATIONS = 5

    def __init__(self):
        self.client = groq_client
        self.tool_executor = ToolExecutor()

    async def run(self, *, message: str, endpoint_result: dict) -> dict:
        # History belongs to this request. Explicitly pass completed/cached data.
        input_items = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"message": message, "endpoint_result": endpoint_result},
                ensure_ascii=False,
            )},
        ]
        documents = []
        for _ in range(self.MAX_ITERATIONS):
            response = await self.client.responses.create(
                model=self.MODEL_NAME, input=input_items, tools=TOOLS,
            )
            input_items.extend(
                item.model_dump(exclude_none=True) for item in response.output
            )
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                if not response.output_text.strip():
                    raise EmptyModelResponseError("Agent returned an empty response")
                return {"answer": response.output_text, "documents": documents}
            for call in calls:
                result = await self.tool_executor.execute(call)
                input_items.append(result)
                if TOOL_REGISTRY[call.name].returns_document:
                    documents.append(json.loads(result["output"]))
        raise AgentLoopLimitError("Agent exceeded maximum iterations")
