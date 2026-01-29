from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 数据库配置
    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "pkos"
    db_password: str = "pkos123"
    db_name: str = "pkos_knowledge"

    # Redis配置
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8080

    # 抖音配置
    douyin_cookies_file: str = "douyin_cookies.txt"

    # ============================================
    # LLM 多模型配置
    # ============================================

    # 默认 LLM 提供商
    llm_default_provider: Literal["openai", "deepseek", "glm", "claude"] = "openai"

    # OpenAI 配置
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # DeepSeek 配置
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # GLM (智谱) 配置
    glm_api_key: Optional[str] = None
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_model: str = "glm-4"

    # Claude 配置
    claude_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-20241022"

    # Telegram Bot 配置
    telegram_bot_token: str
    telegram_bot_username: Optional[str] = None

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def load_llm_config(self) -> dict:
        """
        从环境变量构建 LLM 配置
        保留 JSON 配置文件的向后兼容，但优先使用环境变量
        """
        config = {
            "default": self.llm_default_provider,
            "models": {}
        }

        # OpenAI 配置
        if self.openai_api_key:
            config["models"]["openai"] = {
                "type": "openai",
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "model": self.openai_model
            }

        # DeepSeek 配置
        if self.deepseek_api_key:
            config["models"]["deepseek"] = {
                "type": "openai",
                "api_key": self.deepseek_api_key,
                "base_url": self.deepseek_base_url,
                "model": self.deepseek_model
            }

        # GLM 配置
        if self.glm_api_key:
            config["models"]["glm"] = {
                "type": "openai",
                "api_key": self.glm_api_key,
                "base_url": self.glm_base_url,
                "model": self.glm_model
            }

        # Claude 配置
        if self.claude_api_key:
            config["models"]["claude"] = {
                "type": "claude",
                "api_key": self.claude_api_key,
                "model": self.claude_model
            }

        # 如果没有任何环境变量配置，尝试从旧版 JSON 文件读取
        if not config["models"]:
            import json
            config_path = Path("config/llm_config.json")
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass

        return config

settings = Settings()
