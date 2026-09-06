from openai import AsyncOpenAI
from app.configurations.config import settings

# Calling the Groq LLM by Groq API key
def get_llm_service():
    client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    return LLMService(client)

class LLMService:

    MODEL_NAME = "openai/gpt-oss-120b" # 以后改模型只需要改这里

    def __init__(self,client: AsyncOpenAI):
        self.client = client # AsyncOpenAI 已经包含了API Key， 因此 llm_service.py 不需要再次创建 AsyncOpenAI。

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

        return response.output_text
