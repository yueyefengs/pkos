# 飞书个人知识库机器人 - 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个飞书机器人，接收抖音/B站视频链接，自动下载、转录、LLM优化后保存到飞书多维表格。

**Architecture:** FastAPI服务 + 飞书开放平台API + PostgreSQL/Redis + Docker容器化部署

**Tech Stack:** FastAPI, asyncpg, redis, faster-whisper, yt-dlp, selenium, openai, anthropic

---

## Task 1: 创建项目目录结构

**Files:**
- Create: `config/`
- Create: `bot/`
- Create: `processors/`
- Create: `models/`
- Create: `storage/`
- Create: `temp/`
- Create: `docker/`
- Create: `config/prompts/`

**Step 1: 创建目录结构**

```bash
mkdir -p config/prompts bot processors models storage temp docker logs
```

**Step 2: 验证目录创建**

Run: `ls -la`
Expected: 输出包含 config, bot, processors, models, storage, temp, docker, logs 目录

**Step 3: Commit**

```bash
git add .
git commit -m "chore: create project directory structure"
```

---

## Task 2: 创建Docker配置文件

**Files:**
- Create: `docker/Dockerfile`
- Create: `docker/docker-compose.yml`
- Create: `docker/docker-compose.dev.yml`
- Create: `docker/.dockerignore`

**Step 1: 创建Dockerfile**

```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p temp storage logs

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["uvicorn", "bot.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Step 2: 创建docker-compose.yml（生产版）**

```yaml
version: '3.8'

services:
  bot:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: feishu-knowledge-bot
    ports:
      - "8080:8080"
    env_file:
      - ../.env
    volumes:
      - ../config:/app/config:ro
      - ../temp:/app/temp
      - ../logs:/app/logs
    depends_on:
      - db
      - redis
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
      - CHROME_BIN=/usr/bin/chromium
      - CHROME_DRIVER=/usr/bin/chromedriver
      - DB_HOST=db
      - DB_PORT=5432
      - REDIS_HOST=redis
      - REDIS_PORT=6379

  db:
    image: postgres:15-alpine
    container_name: feishu-knowledge-db
    environment:
      - POSTGRES_USER=feishu
      - POSTGRES_PASSWORD=feishu123
      - POSTGRES_DB=feishu_knowledge
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: feishu-knowledge-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**Step 3: 创建docker-compose.dev.yml（开发版）**

```yaml
version: '3.8'

services:
  bot:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: uvicorn bot.main:app --host 0.0.0.0 --port 8080 --reload
    volumes:
      - ..:/app
      - /app/__pycache__
      - /app/.pytest_cache
    environment:
      - PYTHONUNBUFFERED=1
      - DB_HOST=db
      - DB_PORT=5432
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    ports:
      - "8080:8080"
    depends_on:
      - db
      - redis

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=feishu
      - POSTGRES_PASSWORD=feishu123
      - POSTGRES_DB=feishu_knowledge
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

**Step 4: 创建.dockerignore**

```
.git
.gitignore
.env
.env.local
*.md
docs/
tests/
__pycache__/
*.pyc
.pytest_cache/
.coverage
dist/
```

**Step 5: Commit**

```bash
git add docker/
git commit -m "feat: add Docker configuration"
```

---

## Task 3: 创建配置管理模块

**Files:**
- Create: `config/settings.py`
- Create: `config/llm_config.json`

**Step 1: 创建settings.py**

```python
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
```

**Step 2: 创建llm_config.json**

```json
{
  "default": "openai",
  "models": {
    "openai": {
      "type": "openai",
      "api_key": "sk-xxxxx",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o"
    },
    "deepseek": {
      "type": "openai",
      "api_key": "sk-xxxxx",
      "base_url": "https://api.deepseek.com/v1",
      "model": "deepseek-chat"
    },
    "glm": {
      "type": "openai",
      "api_key": "xxxxx",
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "model": "glm-4"
    },
    "claude": {
      "type": "claude",
      "api_key": "sk-ant-xxxxx",
      "model": "claude-3-5-sonnet-20241022"
    }
  }
}
```

**Step 3: Commit**

```bash
git add config/
git commit -m "feat: add configuration management module"
```

---

## Task 4: 创建数据模型

**Files:**
- Create: `models/task.py`

**Step 1: 创建task.py**

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class TaskStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: Optional[int] = None
    task_id: str = Field(..., description="UUID for the task")
    video_url: str = Field(..., description="Video URL")
    title: Optional[str] = Field(None, description="Video title")
    platform: Optional[str] = Field(None, description="Video platform (douyin/bilibili)")
    status: TaskStatus = Field(default=TaskStatus.PROCESSING, description="Task status")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = Field(None, description="Error message if failed")
    content: Optional[str] = Field(None, description="Processed content")

class TaskCreate(BaseModel):
    task_id: str
    video_url: str
    platform: Optional[str] = None

class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    content: Optional[str] = None
    completed_at: Optional[datetime] = None
```

**Step 2: Commit**

```bash
git add models/
git commit -m "feat: add task data models"
```

---

## Task 5: 创建PostgreSQL存储模块

**Files:**
- Create: `storage/postgres.py`

**Step 1: 创建postgres.py**

```python
import asyncpg
from typing import Optional, List
from datetime import datetime
from config.settings import settings
from models.task import Task, TaskCreate, TaskStatus

class PostgresStorage:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """连接到PostgreSQL数据库"""
        self.pool = await asyncpg.create_pool(settings.database_url)
        await self._init_db()

    async def disconnect(self):
        """关闭数据库连接"""
        if self.pool:
            await self.pool.close()

    async def _init_db(self):
        """初始化数据库表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(36) UNIQUE NOT NULL,
            video_url TEXT NOT NULL,
            title VARCHAR(500),
            platform VARCHAR(50),
            status VARCHAR(20) DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            error_message TEXT,
            content TEXT
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(create_table_sql)

    async def create_task(self, task: TaskCreate) -> Task:
        """创建新任务"""
        now = datetime.now()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO tasks (task_id, video_url, platform, created_at, updated_at, status)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                task.task_id, task.video_url, task.platform, now, now, TaskStatus.PROCESSING
            )
        return self._record_to_task(record)

    async def get_task(self, task_id: str) -> Optional[Task]:
        """根据task_id获取任务"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM tasks WHERE task_id = $1", task_id
            )
        return self._record_to_task(record) if record else None

    async def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务"""
        updates = []
        values = []
        param_idx = 1

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1

        if not updates:
            return await self.get_task(task_id)

        updates.append("updated_at = NOW()")
        values.append(task_id)

        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ${param_idx}"

        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(sql, *values)
        return self._record_to_task(record) if record else None

    def _record_to_task(self, record) -> Task:
        """将数据库记录转换为Task对象"""
        return Task(
            id=record["id"],
            task_id=record["task_id"],
            video_url=record["video_url"],
            title=record["title"],
            platform=record["platform"],
            status=TaskStatus(record["status"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            completed_at=record["completed_at"],
            error_message=record["error_message"],
            content=record["content"]
        )

# 全局存储实例
storage = PostgresStorage()
```

**Step 2: Commit**

```bash
git add storage/
git commit -m "feat: add PostgreSQL storage module"
```

---

## Task 6: 创建LLM客户端

**Files:**
- Create: `processors/llm_client.py`

**Step 1: 创建llm_client.py**

```python
from typing import Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import settings

class LLMClient:
    def __init__(self):
        self.config = settings.load_llm_config()
        self.default_model = self.config.get("default", "openai")
        self.clients = {}
        self._init_clients()

    def _init_clients(self):
        """初始化LLM客户端"""
        models = self.config.get("models", {})

        for name, model_config in models.items():
            model_type = model_config.get("type", "openai")

            if model_type == "openai":
                self.clients[name] = AsyncOpenAI(
                    api_key=model_config.get("api_key"),
                    base_url=model_config.get("base_url", "https://api.openai.com/v1")
                )
            elif model_type == "claude":
                self.clients[name] = AsyncAnthropic(
                    api_key=model_config.get("api_key")
                )

    async def optimize_content(self, content: str, prompt: str = "") -> str:
        """优化内容（修正错别字、智能分段）"""
        system_prompt = prompt or """你是一个专业的内容编辑。你的任务是优化转录文本：
1. 修正错别字和语音识别错误
2. 智能分段，按照语义和逻辑划分段落
3. 保持原意不变，不要添加或删减内容
4. 保持语言风格一致"""

        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})

        if model_config.get("type") == "claude":
            response = await self.clients[model_name].messages.create(
                model=model_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=8192,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"请优化以下内容：\n\n{content}"}
                ]
            )
            return response.content[0].text
        else:
            response = await self.clients[model_name].chat.completions.create(
                model=model_config.get("model", "gpt-4o"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请优化以下内容：\n\n{content}"}
                ],
                max_tokens=8192
            )
            return response.choices[0].message.content or content

    async def classify_content(self, content: str) -> str:
        """内容分类"""
        prompt = "请分析以下内容的主要类型：理论解释、技能教程、金融风险、人物传记、观点分析。只回答类型名称。"

        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})

        if model_config.get("type") == "claude":
            response = await self.clients[model_name].messages.create(
                model=model_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=100,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n内容：{content[:1000]}"}
                ]
            )
            return response.content[0].text.strip()
        else:
            response = await self.clients[model_name].chat.completions.create(
                model=model_config.get("model", "gpt-4o"),
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n内容：{content[:1000]}"}
                ],
                max_tokens=100
            )
            return response.choices[0].message.content or "其他"

# 全局LLM客户端实例
llm_client = LLMClient()
```

**Step 2: Commit**

```bash
git add processors/llm_client.py
git commit -m "feat: add LLM client with multi-model support"
```

---

## Task 7: 创建视频下载器

**Files:**
- Create: `processors/video_downloader.py`

**Step 1: 创建video_downloader.py**

```python
import re
import asyncio
from typing import Optional, Tuple
from pathlib import Path
from config.settings import settings

class VideoDownloader:
    def __init__(self):
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)

    def detect_platform(self, url: str) -> Optional[str]:
        """检测视频平台"""
        if "douyin.com" in url:
            return "douyin"
        elif "bilibili.com" in url:
            return "bilibili"
        return None

    async def download(self, url: str) -> Tuple[str, str]:
        """下载视频并提取音频

        Returns:
            (音频文件路径, 视频标题)
        """
        platform = self.detect_platform(url)

        if platform == "bilibili":
            return await self._download_bilibili(url)
        elif platform == "douyin":
            return await self._download_douyin(url)
        else:
            raise ValueError(f"不支持的平台: {platform}")

    async def _download_bilibili(self, url: str) -> Tuple[str, str]:
        """下载B站视频"""
        import yt_dlp

        output_template = str(self.temp_dir / "bilibili_%(title)s.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192'
            }],
            'postprocessor_args': ['-ac', '1', '-ar', '16000'],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'unknown')

        # 查找生成的音频文件
        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            audio_file = self.temp_dir / f"bilibili_{title}.{ext}"
            if audio_file.exists():
                return str(audio_file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    async def _download_douyin(self, url: str) -> Tuple[str, str]:
        """下载抖音视频"""
        import yt_dlp

        # 抖音通常可以用yt-dlp，如果需要cookies
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.temp_dir / "douyin_%(id)s.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192'
            }],
            'postprocessor_args': ['-ac', '1', '-ar', '16000'],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        # 检查cookies文件
        cookies_file = Path(settings.douyin_cookies_file)
        if cookies_file.exists():
            ydl_opts['cookiefile'] = str(cookies_file)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', info.get('description', 'unknown')[:50])

        # 查找生成的音频文件
        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            for file in self.temp_dir.glob(f"douyin_*.{ext}"):
                return str(file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    def _sanitize_title(self, title: str) -> str:
        """清理标题为安全的文件名"""
        safe = re.sub(r"[^\w\-\s]", "", title)
        safe = re.sub(r"\s+", "_", safe).strip("._-")
        return safe[:80] or "untitled"

# 全局下载器实例
video_downloader = VideoDownloader()
```

**Step 2: Commit**

```bash
git add processors/video_downloader.py
git commit -m "feat: add video downloader for Douyin and Bilibili"
```

---

## Task 8: 创建转录器

**Files:**
- Create: `processors/transcriber.py`

**Step 1: 创建transcriber.py**

```python
from typing import Optional
from faster_whisper import WhisperModel
from pathlib import Path

class Transcriber:
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model: Optional[WhisperModel] = None
        self.detected_language: Optional[str] = None

    def _load_model(self):
        """延迟加载模型"""
        if self.model is None:
            compute_type = "float16" if self.device == "cuda" else "int8"
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type
            )

    def transcribe(self, audio_path: str) -> str:
        """转录音频文件

        Args:
            audio_path: 音频文件路径

        Returns:
            转录文本
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        self._load_model()

        segments, info = self.model.transcribe(
            str(audio_file),
            beam_size=5,
            best_of=5,
            temperature=[0.0, 0.2, 0.4],
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 900,
                "speech_pad_ms": 300
            },
            no_speech_threshold=0.7,
            compression_ratio_threshold=2.3,
            condition_on_previous_text=False
        )

        self.detected_language = info.language

        # 收集文本
        text_only_lines = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                text_only_lines.append(text)

        # 合并段落
        plain_text = "\n\n".join(text_only_lines)

        return plain_text

# 全局转录器实例
transcriber = Transcriber()
```

**Step 2: Commit**

```bash
git add processors/transcriber.py
git commit -m "feat: add Whisper transcriber module"
```

---

## Task 9: 创建内容处理器

**Files:**
- Create: `processors/content_processor.py`

**Step 1: 创建content_processor.py**

```python
from pathlib import Path
from processors.llm_client import llm_client

class ContentProcessor:
    def __init__(self):
        self.prompts_dir = Path("config/prompts")

    def load_prompt(self, prompt_name: str) -> str:
        """加载prompt模板"""
        prompt_file = self.prompts_dir / f"{prompt_name}.md"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    async def process(self, content: str, title: str) -> str:
        """处理内容：优化、格式化

        Args:
            content: 原始转录内容
            title: 视频标题

        Returns:
            处理后的内容
        """
        # 首先分类内容
        content_type = await llm_client.classify_content(content)

        # 加载对应的prompt
        prompt = self.load_prompt(content_type)

        # 使用LLM优化内容
        optimized_content = await llm_client.optimize_content(content, prompt)

        # 格式化输出
        formatted_content = f"# {title}\n\n{optimized_content}"

        return formatted_content

# 全局内容处理器实例
content_processor = ContentProcessor()
```

**Step 2: Commit**

```bash
git add processors/content_processor.py
git add processors/__init__.py
git commit -m "feat: add content processor module"
```

---

## Task 10: 创建飞书客户端

**Files:**
- Create: `bot/feishu_client.py`

**Step 1: 创建feishu_client.py**

```python
import hashlib
import hmac
import base64
import json
import httpx
from typing import Optional
from config.settings import settings

class FeishuClient:
    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.encrypt_key = settings.feishu_encrypt_key
        self.bitable_token = settings.feishu_bitable_token
        self.bitable_table_id = settings.feishu_bitable_table_id
        self.tenant_access_token: Optional[str] = None
        self.base_url = "https://open.feishu.cn/open-apis"

    async def get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        if self.tenant_access_token:
            return self.tenant_access_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            self.tenant_access_token = data["tenant_access_token"]
            return self.tenant_access_token

    def verify_event(self, timestamp: str, nonce: str, body: str, signature: str) -> bool:
        """验证飞书事件签名"""
        if not self.encrypt_key:
            return True  # 如果没有配置加密密钥，跳过验证

        key = base64.b64decode(self.encrypt_key)
        message = f"{timestamp}{nonce}{body}".encode()
        expected_signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        return expected_signature == signature

    async def send_message(self, receive_id: str, msg_type: str = "text", content: str = ""):
        """发送消息"""
        token = await self.get_tenant_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/im/v1/messages?receive_id_type=open_id",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "receive_id": receive_id,
                    "msg_type": msg_type,
                    "content": json.dumps({"text": content})
                }
            )
            response.raise_for_status()
            return response.json()

    async def create_record(self, title: str, video_url: str, content: str) -> str:
        """在多维表格中创建记录

        Returns:
            记录ID
        """
        token = await self.get_tenant_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.bitable_table_id}/records",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "fields": {
                        "标题": title,
                        "来源URL": video_url,
                        "处理状态": "已完成",
                        "文稿内容": content
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"]["record"]["record_id"]

# 全局飞书客户端实例
feishu_client = FeishuClient()
```

**Step 2: Commit**

```bash
git add bot/feishu_client.py
git commit -m "feat: add Feishu API client"
```

---

## Task 11: 创建事件处理和主API

**Files:**
- Create: `bot/webhook.py`
- Create: `bot/main.py`
- Create: `bot/__init__.py`
- Create: `models/__init__.py`
- Create: `storage/__init__.py`
- Create: `processors/__init__.py`
- Create: `config/__init__.py`

**Step 1: 创建webhook.py**

```python
import asyncio
import uuid
from fastapi import BackgroundTasks
from typing import Dict, Any
from bot.feishu_client import feishu_client
from storage.postgres import storage
from processors.video_downloader import video_downloader
from processors.transcriber import transcriber
from processors.content_processor import content_processor
from models.task import TaskCreate

class WebhookHandler:
    async def handle_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理飞书消息事件"""
        chat_type = event.get("chat_type", "")
        content = event.get("content", {})
        message_id = event.get("message_id", "")
        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

        if chat_type == "group":
            at_text = content.get("at_users", "")
            if not at_text:  # 没有@机器人，忽略
                return {"code": 0}

        # 提取视频URL
        text = content.get("text", "")
        video_url = self._extract_video_url(text)

        if not video_url:
            await feishu_client.send_message(
                sender_id,
                content="请发送有效的抖音或B站视频链接"
            )
            return {"code": 0}

        # 验证平台
        platform = video_downloader.detect_platform(video_url)
        if not platform:
            await feishu_client.send_message(
                sender_id,
                content="目前仅支持抖音和B站视频"
            )
            return {"code": 0}

        # 创建任务
        task_id = str(uuid.uuid4())
        await storage.connect()
        task = await storage.create_task(
            TaskCreate(task_id=task_id, video_url=video_url, platform=platform)
        )
        await storage.disconnect()

        # 回复用户
        await feishu_client.send_message(
            sender_id,
            content=f"收到链接，正在处理中...\n平台: {platform}\n任务ID: {task_id[:8]}"
        )

        # 异步处理视频
        asyncio.create_task(self._process_video(task_id, video_url, sender_id))

        return {"code": 0}

    async def _process_video(self, task_id: str, video_url: str, user_id: str):
        """异步处理视频"""
        try:
            await storage.connect()

            # 1. 下载视频
            await feishu_client.send_message(user_id, content="正在下载视频...")
            audio_path, title = await video_downloader.download(video_url)

            # 2. 转录
            await feishu_client.send_message(user_id, content="正在转录音频...")
            raw_content = transcriber.transcribe(audio_path)

            # 3. 内容处理
            await feishu_client.send_message(user_id, content="正在优化内容...")
            processed_content = await content_processor.process(raw_content, title)

            # 4. 保存到多维表格
            await feishu_client.send_message(user_id, content="正在保存到知识库...")
            record_id = await feishu_client.create_record(title, video_url, processed_content)

            # 5. 更新任务状态
            await storage.update_task(
                task_id,
                title=title,
                status="completed",
                content=processed_content
            )

            # 6. 发送完成通知
            await feishu_client.send_message(
                user_id,
                content=f"处理完成！\n\n标题: {title}\n已保存到多维表格"
            )

        except Exception as e:
            await storage.update_task(task_id, status="failed", error_message=str(e))
            await feishu_client.send_message(
                user_id,
                content=f"处理失败: {str(e)}"
            )
        finally:
            await storage.disconnect()

    def _extract_video_url(self, text: str) -> str:
        """从文本中提取视频URL"""
        import re
        # 匹配http/https开头的URL
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        return urls[0] if urls else ""

# 全局Webhook处理器实例
webhook_handler = WebhookHandler()
```

**Step 2: 创建main.py**

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from config.settings import settings
from bot.feishu_client import feishu_client
from bot.webhook import webhook_handler

app = FastAPI(title="Feishu Knowledge Bot", version="1.0.0")

@app.on_event("startup")
async def startup():
    """服务启动时的初始化"""
    await feishu_client.get_tenant_access_token()

@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}

@app.post("/feishu/events")
async def handle_feishu_event(request: Request):
    """处理飞书事件"""
    body = await request.body()
    data = await request.json()

    # 验证URL签名
    if "url_verify" in data:
        challenge = data.get("challenge", "")
        return JSONResponse(content={"challenge": challenge})

    # 验证事件签名
    headers = request.headers
    timestamp = headers.get("X-Lark-Request-Timestamp", "")
    nonce = headers.get("X-Lark-Request-Nonce", "")
    signature = headers.get("X-Lark-Signature", "")

    if not feishu_client.verify_event(timestamp, nonce, body.decode(), signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 处理事件
    event = data.get("event", {})
    event_type = event.get("type", "")

    if event_type == "message.receive_v1":
        result = await webhook_handler.handle_message(event)

    return JSONResponse(content={"code": 0, "msg": "success"})

if __name__ == "__main__":
    uvicorn.run(
        "bot.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
```

**Step 3: 创建__init__.py文件**

```bash
# 创建各个模块的__init__.py
touch bot/__init__.py models/__init__.py storage/__init__.py processors/__init__.py config/__init__.py
```

**Step 4: Commit**

```bash
git add bot/ models/__init__.py storage/__init__.py processors/__init__.py config/__init__.py
git commit -m "feat: add webhook handler and main API"
```

---

## Task 12: 创建requirements.txt和.env.example

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`

**Step 1: 创建requirements.txt**

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
asyncpg==0.29.0
redis==5.0.1
faster-whisper==1.0.0
yt-dlp==2024.1.1
selenium==4.17.2
openai==1.10.0
anthropic==0.18.1
pydantic-settings==2.1.0
python-dotenv==1.0.0
```

**Step 2: 创建.env.example**

```env
# 飞书应用配置
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_BOT_NAME=知识助手
FEISHU_ENCRYPT_KEY=xxxxx

# 飞书多维表格配置
FEISHU_BITABLE_TOKEN=xxxxx
FEISHU_BITABLE_TABLE_ID=xxxxx

# 数据库配置
DB_HOST=db
DB_PORT=5432
DB_USER=feishu
DB_PASSWORD=feishu123
DB_NAME=feishu_knowledge

# Redis配置
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# 服务配置
HOST=0.0.0.0
PORT=8080

# 抖音配置
DOUYIN_COOKIES_FILE=douyin_cookies.txt

# LLM配置
LLM_CONFIG_FILE=config/llm_config.json
```

**Step 3: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add requirements and env example"
```

---

## Task 13: 创建README文档

**Files:**
- Create: `README.md`

**Step 1: 创建README.md**

```markdown
# 飞书个人知识库机器人

通过飞书机器人接收抖音/B站视频链接，自动下载、转录、LLM优化后保存到飞书多维表格。

## 功能特性

- 支持抖音、B站视频下载
- Whisper语音识别转录
- LLM智能优化文稿
- 多LLM支持：OpenAI、DeepSeek、GLM、Claude
- 自动保存到飞书多维表格
- 异步处理，实时进度反馈

## 快速开始

### 1. 配置环境变量

复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下信息：
- 飞书应用ID和密钥
- 飞书多维表格token和table_id
- LLM API密钥

### 2. 配置飞书应用

1. 在飞书开放平台创建自建应用
2. 开启机器人能力，获取权限：获取与发送消息、读写多维表格
3. 配置事件订阅：`/feishu/events`

### 3. 启动服务

开发模式：

```bash
docker-compose -f docker/docker-compose.dev.yml up
```

生产模式：

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 4. 使用

在飞书中@机器人发送视频链接，机器人会自动处理并保存到多维表格。

## 目录结构

```
feishu-knowledge-bot/
├── bot/              # 飞书机器人模块
├── processors/       # 视频处理模块
├── models/           # 数据模型
├── storage/          # 数据库存储
├── config/           # 配置文件
├── docker/           # Docker配置
└── temp/             # 临时文件
```

## License

MIT
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README documentation"
```

---

## 完成后

所有任务完成后，创建prompt模板文件（从PKOS的prompt目录复制），然后推送分支：

```bash
git push -u origin feature/feishu-knowledge-bot
```
