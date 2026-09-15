from openai import AsyncOpenAI

from app.configurations.config import settings


# Groq offers an OpenAI-compatible endpoint, so the standard client is reused
# by changing `base_url`.  Credentials stay in settings rather than source code.
groq_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
