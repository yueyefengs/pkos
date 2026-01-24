from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import json
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 飞书应用配置
    feishu_app_id: str
    feishu_app_secret: str
    feishu_bot_name: str = "知识助手"
    feishu_encrypt_key: Optional[str] = None

    # 飞书多维表格配置
    feishu_bitable_token: str
    feishu_bitable_table_id: str

    # 数据库配置
    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "feishu"
    db_password: str = "feishu123"
    db_name: str = "feishu_knowledge"

    # Redis配置
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8080

    # 抖音配置
    douyin_cookies_file: str = "douyin_cookies.txt"

    # LLM配置
    llm_config_file: str = "config/llm_config.json"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def load_llm_config(self) -> dict:
        config_path = Path(self.llm_config_file)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"default": "openai", "models": {}}

settings = Settings()
