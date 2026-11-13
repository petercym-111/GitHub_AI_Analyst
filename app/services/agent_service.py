import json
from openai import AsyncOpenAI

from app.clients.groq_client import groq_client
from app.prompts.agent import SYSTEM_PROMPT
from app.services.tool_executor import ToolExecutor
from app.services.tool.tool_schemas import TOOLS
from app.services.tool_registry import TOOL_REGISTRY
from app.exceptions import (
    AgentExecutionError,
    AgentLoopLimitError,
    EmptyModelResponseError,
)
# agent loop for the optional message, if message received this file will be trigger

class AgentService:
    MODEL_NAME = "openai/gpt-oss-120b"
    MAX_ITERATIONS = 5

    def __init__(self):
        self.client = groq_client
        self.tool_executor = ToolExecutor()

    async def run(self, *, message: str, endpoint_result: dict) -> dict:
        # 1. 建立本次请求专属的 history，放入 message 和已完成/缓存的 endpoint 数据。
        # 当这个 function 被触发时，传过来的数据就是初始内容
        input_items = [ # 目前 input_items 里的内容是不会被修改的，这里说的修改不是说初始内容被修改了，初始内容还是原封不动的，而后续内容只是被append 到input_items 这个list 的末尾罢了
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"message": message, "endpoint_result": endpoint_result},
                ensure_ascii=False,
            )},
        ]
        documents = []
        try:
            # 2. 重复请求模型，但用 MAX_ITERATIONS 限制 loop 次数。
            for iteration in range(self.MAX_ITERATIONS):
                print(
                    f"\n========== ITERATION {iteration + 1} =========="
                )

                print("INPUT:")
                print(
                    json.dumps(
                        input_items,
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                print("CALLING GROQ...")
                print("TOOLS:")
                print(TOOLS)

                print("TYPE:")
                print(type(TOOLS))

                print("TOOL TYPE:")
                print(type(TOOLS[0]))

                print("TOOL:")
                print(TOOLS[0])

                response = await self.client.responses.create(
                    model=self.MODEL_NAME, input=input_items, tools=TOOLS,
                )

                print("GROQ RESPONSE RECEIVED")

                print("OUTPUT:")
                print(response.output)

                input_items.extend(
                    item.model_dump(exclude_none=True) for item in response.output
                )
                calls = [item for item in response.output if item.type == "function_call"]

                if not calls:
                    # 3. 没有 function_call 即结束 loop；若文本为空则视为失败。
                    if not response.output_text.strip():
                        raise EmptyModelResponseError("Agent returned an empty response")
                    return {"answer": response.output_text, "documents": documents}

                # 4. 执行模型请求的工具，并把带对应 call_id 的结果放进下一轮 history。
                # 为什么需要 call_id ：因为即使多个工具并行执行、结果按不同顺序返回，也能把每个结果对应到正确的 function_call。
                # 一次模型响应可能包含多个工具调用，程序执行工具的顺序也不一定和返回结果的顺序一致，因此依靠 list 里的位置匹配很可能出错，所以才需要 call_id 来精准匹配
                for call in calls:
                    result = await self.tool_executor.execute(call)
                    input_items.append(result)
                    if TOOL_REGISTRY[call.name].returns_document:
                        # 保存成功创建的文档信息，后续失败时仍可返回文件信息。
                        documents.append(json.loads(result["output"]))

            # 5. 达到轮数上限仍未得到最终文本时，可选 Agent 任务失败。
            raise AgentLoopLimitError("Agent exceeded maximum iterations")
        except AgentExecutionError:
            raise
        except Exception as exc:
            # 将底层异常与已创建文档一起保留，供 endpoint 构造失败响应。
            raise AgentExecutionError(exc, documents) from exc
