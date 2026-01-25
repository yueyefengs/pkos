#!/usr/bin/env python3
"""
文档总结服务 - 后端 API
支持多种 LLM: OpenAI, Claude, DeepSeek, GLM 等
"""

import os
import json
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="文档总结服务")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 配置文件路径
CONFIG_FILE = "config.json"


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str  # openai, claude, deepseek, glm
    api_key: str
    base_url: Optional[str] = None
    model: str
    temperature: float = 0.7
    max_tokens: int = 4000


class SummaryRequest(BaseModel):
    """总结请求"""
    text: str
    prompt: str
    config: LLMConfig


class ConfigData(BaseModel):
    """配置数据"""
    configs: List[LLMConfig]
    defaultPrompt: str


# 预设的 LLM 配置模板
PRESET_CONFIGS = {
    "openai": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "claude": {
        "provider": "claude",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-20241022",
    },
    "deepseek": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "glm": {
        "provider": "glm",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "oneapi": {
        "provider": "openai",
        "base_url": "https://oneapi.basevec.com/v1",
        "model": "gpt-4o-mini",
    },
}


def load_config() -> ConfigData:
    """加载配置"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return ConfigData(**data)
    else:
        # 默认配置
        return ConfigData(
            configs=[],
            defaultPrompt="请对以下内容进行总结，提取关键信息和要点：\n\n{text}"
        )


def save_config(config: ConfigData):
    """保存配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)


async def call_openai_compatible(text: str, prompt: str, config: LLMConfig) -> str:
    """调用 OpenAI 兼容的 API"""
    messages = [
        {"role": "user", "content": prompt.replace("{text}", text)}
    ]

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    url = f"{config.base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def call_claude(text: str, prompt: str, config: LLMConfig) -> str:
    """调用 Claude API"""
    import anthropic

    client = anthropic.Anthropic(api_key=config.api_key)

    message = client.messages.create(
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        messages=[
            {"role": "user", "content": prompt.replace("{text}", text)}
        ]
    )

    return message.content[0].text


@app.get("/api/config")
async def get_config():
    """获取配置"""
    config = load_config()
    return {
        "configs": config.configs,
        "defaultPrompt": config.defaultPrompt,
        "presets": PRESET_CONFIGS
    }


@app.post("/api/config")
async def update_config(data: ConfigData):
    """更新配置"""
    save_config(data)
    return {"success": True}


@app.post("/api/summarize")
async def summarize(request: SummaryRequest):
    """总结文档"""
    try:
        config = request.config

        logger.info(f"使用 {config.provider} 进行总结，模型: {config.model}")

        if config.provider == "claude":
            summary = await call_claude(request.text, request.prompt, config)
        else:
            # OpenAI 兼容接口（包括 DeepSeek, GLM, OneAPI 等）
            summary = await call_openai_compatible(request.text, request.prompt, config)

        return {
            "success": True,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"总结失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/test")
async def test_connection(config: LLMConfig):
    """测试连接"""
    try:
        test_prompt = "请回复'连接成功'"
        test_text = "测试"

        if config.provider == "claude":
            result = await call_claude(test_text, test_prompt, config)
        else:
            result = await call_openai_compatible(test_text, test_prompt, config)

        return {
            "success": True,
            "message": "连接成功",
            "response": result[:100]
        }
    except Exception as e:
        logger.error(f"连接测试失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files")
async def list_files(directory: str = "outputs"):
    """列出可用的文本文件"""
    try:
        if not os.path.exists(directory):
            return {"files": []}

        files = []
        for file in os.listdir(directory):
            if file.endswith(('.md', '.txt')):
                file_path = os.path.join(directory, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                files.append({
                    "name": file,
                    "path": file_path,
                    "preview": content[:500] + "..." if len(content) > 500 else content,
                    "size": len(content)
                })
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/file/{filename}")
async def get_file(filename: str, directory: str = "outputs"):
    """获取文件内容"""
    try:
        file_path = os.path.join(directory, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {"name": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
