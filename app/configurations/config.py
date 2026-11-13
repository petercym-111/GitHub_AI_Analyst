from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    github_token: str
    GROQ_API_KEY: str
    DATABASE_URL: str
    ANALYSIS_CACHE_TTL_SECONDS: int = Field(default=86400, gt=0) # 当前用户的分析缓存只要在 database 超过 86400 秒，就会重新分析不再复用当前缓存，
                                                                 # 无论另一个条件（get_analysis_version）有没有更新

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
