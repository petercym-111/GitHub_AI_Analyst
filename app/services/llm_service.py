from app.clients.groq_client import groq_client
from app.exceptions import EmptyModelResponseError
# Single Responses request for repository analysis; no tools or agent loop.

class LLMService:

    MODEL_NAME = "openai/gpt-oss-120b" # 以后改模型只需要改这里

    def __init__(self):
        self.client = groq_client # AsyncOpenAI 已经包含了API Key， 因此 llm_service.py 不需要再次创建 AsyncOpenAI。

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        # 通用模型调用：接收 prompt，沿用 JSON 模式并返回原始响应文本。
        # 具体业务的字段筛选、prompt 组装和结果解析由调用方负责。
        response = (
            await self.client.responses.create(
                model=self.MODEL_NAME,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                text={
                    "format": {"type": "json_object"}
                },
            )
        )

        if not response.output_text.strip():
            raise EmptyModelResponseError("Analysis model returned an empty response")
        return response.output_text
