from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./aidrama.db"

    # LLM
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    LLM_API_KEY: Optional[str] = None       # 通用 key，优先级高于 OPENAI_API_KEY
    LLM_BASE_URL: Optional[str] = None      # OpenAI 兼容接口地址，如硅基流动
    LLM_PROVIDER: str = "anthropic"         # "anthropic" | "openai"
    LLM_MODEL: str = "claude-3-5-sonnet-20241022"

    # Seedream（图片生成）
    SEEDREAM_API_KEY: Optional[str] = None
    SEEDREAM_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"

    # Seedance（视频生成）
    SEEDANCE_API_KEY: Optional[str] = None
    SEEDANCE_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    SEEDANCE_MODEL: str = "doubao-seedance-1-5-pro-251215"

    # 文件存储
    ASSETS_DIR: str = "./assets"
    BACKEND_URL: str = "http://localhost:8000"
    MAX_CONCURRENT_VIDEO_TASKS: int = 10
    VIDEO_RETRY_LIMIT: int = 3

    # Redis（Celery）
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
