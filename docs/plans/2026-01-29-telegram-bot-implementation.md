# Telegram Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有的飞书机器人替换为Telegram bot，支持视频转录、多轮对话、学习模式和进度追踪

**Architecture:**
- 使用 python-telegram-bot (PTB) 库的 Long Polling 模式接收消息
- 保留现有的视频处理、转录、LLM处理逻辑
- 新增会话管理（工作区）、学习模式、进度追踪功能
- 使用PostgreSQL存储任务和学习进度，Redis缓存用户会话状态

**Tech Stack:**
- python-telegram-bot (v20+)
- FastAPI (保留，可选的webhook端点)
- PostgreSQL (扩展表结构)
- Redis (会话状态管理)
- 复用: faster-whisper, yt-dlp, openai, anthropic

---

## 任务概览

1. **环境准备和依赖安装**
2. **数据库扩展 - 学习进度表**
3. **Telegram客户端核心**
4. **会话管理器（工作区）**
5. **命令处理器**
6. **消息路由和URL检测**
7. **学习模式实现**
8. **内容分析功能（outline/summary/qa/extend）**
9. **进度追踪功能**
10. **主程序入口和启动脚本**
11. **配置文件更新**
12. **测试和文档**

---

## Task 1: 环境准备和依赖安装

**Files:**
- Modify: `requirements.txt`
- Create: `.env.example` (添加Telegram配置)

**Step 1: 更新requirements.txt**

添加telegram bot相关依赖：

```txt
# 在文件末尾添加
python-telegram-bot[all]==20.8
redis
aioredis
```

**Step 2: 安装依赖**

Run: `pip install -r requirements.txt`
Expected: 成功安装所有包

**Step 3: 更新.env.example**

```bash
# 在.env.example中添加Telegram配置
cat >> .env.example << 'EOF'

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username

# Redis Configuration (for session management)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
EOF
```

**Step 4: 创建本地.env文件**

Run: `cp .env.example .env`
然后编辑.env文件，填入实际的Telegram bot token: `8047869413:AAGp4OGgnP0uOHUMQ7nCx0J36-x2XnYx1qU`

**Step 5: 验证配置**

Run: `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN'))"`
Expected: 输出bot token

**Step 6: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add telegram-bot dependencies and config"
```

---

## Task 2: 数据库扩展 - 学习进度表

**Files:**
- Modify: `storage/postgres.py`
- Modify: `models/task.py`

**Step 1: 创建学习进度模型**

在 `models/task.py` 中添加：

```python
# 在文件末尾添加

from typing import List

class LearningStatus(str, Enum):
    NOT_STARTED = "not_started"
    LEARNING = "learning"
    MASTERED = "mastered"

class ConceptStatus(str, Enum):
    UNDERSTANDING = "understanding"
    STRUGGLING = "struggling"
    MASTERED = "mastered"

class LearningProgress(BaseModel):
    id: Optional[int] = None
    user_id: str = Field(..., description="Telegram用户ID")
    task_id: str = Field(..., description="关联的任务ID")
    status: LearningStatus = Field(default=LearningStatus.NOT_STARTED)
    started_at: Optional[datetime] = None
    last_study_at: Optional[datetime] = None
    total_study_time: int = Field(default=0, description="总学习时长（分钟）")
    questions_asked: int = Field(default=0, description="提问次数")
    mastery_level: int = Field(default=0, description="掌握程度 0-100")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ConceptMastery(BaseModel):
    id: Optional[int] = None
    progress_id: int = Field(..., description="关联的学习进度ID")
    concept_name: str = Field(..., description="概念名称")
    status: ConceptStatus = Field(default=ConceptStatus.UNDERSTANDING)
    understanding_level: int = Field(default=0, description="理解程度 0-100")
    first_learned_at: Optional[datetime] = None
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    review_count: int = Field(default=0)

class LearningCheckpoint(BaseModel):
    id: Optional[int] = None
    progress_id: int
    checkpoint_data: dict = Field(default_factory=dict, description="检查点快照数据")
    created_at: Optional[datetime] = None
```

**Step 2: 扩展PostgresStorage类**

在 `storage/postgres.py` 的 `_init_db` 方法中添加表创建SQL：

```python
# 在 _init_db 方法中的 create_table_sql 后添加

        create_progress_table_sql = """
        CREATE TABLE IF NOT EXISTS learning_progress (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            task_id VARCHAR(36) NOT NULL,
            status VARCHAR(20) DEFAULT 'not_started',
            started_at TIMESTAMP,
            last_study_at TIMESTAMP,
            total_study_time INT DEFAULT 0,
            questions_asked INT DEFAULT 0,
            mastery_level INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, task_id)
        );
        """

        create_concept_table_sql = """
        CREATE TABLE IF NOT EXISTS concept_mastery (
            id SERIAL PRIMARY KEY,
            progress_id INT REFERENCES learning_progress(id) ON DELETE CASCADE,
            concept_name VARCHAR(200) NOT NULL,
            status VARCHAR(20) DEFAULT 'understanding',
            understanding_level INT DEFAULT 0,
            first_learned_at TIMESTAMP,
            last_reviewed_at TIMESTAMP,
            next_review_at TIMESTAMP,
            review_count INT DEFAULT 0
        );
        """

        create_checkpoint_table_sql = """
        CREATE TABLE IF NOT EXISTS learning_checkpoints (
            id SERIAL PRIMARY KEY,
            progress_id INT REFERENCES learning_progress(id) ON DELETE CASCADE,
            checkpoint_data JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_table_sql)
            await conn.execute(create_progress_table_sql)
            await conn.execute(create_concept_table_sql)
            await conn.execute(create_checkpoint_table_sql)
```

**Step 3: 添加学习进度CRUD方法**

在 `PostgresStorage` 类中添加：

```python
    # 学习进度管理方法

    async def get_or_create_progress(self, user_id: str, task_id: str) -> dict:
        """获取或创建学习进度"""
        async with self.pool.acquire() as conn:
            # 尝试获取
            record = await conn.fetchrow(
                "SELECT * FROM learning_progress WHERE user_id = $1 AND task_id = $2",
                user_id, task_id
            )

            if record:
                return dict(record)

            # 不存在则创建
            now = datetime.now()
            record = await conn.fetchrow(
                """
                INSERT INTO learning_progress (user_id, task_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                user_id, task_id, now, now
            )
            return dict(record)

    async def update_progress(self, user_id: str, task_id: str, **kwargs) -> Optional[dict]:
        """更新学习进度"""
        updates = []
        values = []
        param_idx = 1

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1

        if not updates:
            return None

        updates.append("updated_at = NOW()")
        values.extend([user_id, task_id])

        sql = f"""
            UPDATE learning_progress
            SET {', '.join(updates)}
            WHERE user_id = ${param_idx} AND task_id = ${param_idx + 1}
            RETURNING *
        """

        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(sql, *values)
        return dict(record) if record else None

    async def get_user_progress_list(self, user_id: str, limit: int = 10) -> List[dict]:
        """获取用户的学习进度列表"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT lp.*, t.title, t.platform
                FROM learning_progress lp
                JOIN tasks t ON lp.task_id = t.task_id
                WHERE lp.user_id = $1
                ORDER BY lp.last_study_at DESC NULLS LAST, lp.created_at DESC
                LIMIT $2
                """,
                user_id, limit
            )
        return [dict(r) for r in records]

    async def add_concept(self, progress_id: int, concept_name: str) -> dict:
        """添加概念到学习进度"""
        now = datetime.now()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO concept_mastery (progress_id, concept_name, first_learned_at)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                progress_id, concept_name, now
            )
        return dict(record)

    async def get_concepts_by_progress(self, progress_id: int) -> List[dict]:
        """获取学习进度的所有概念"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT * FROM concept_mastery WHERE progress_id = $1 ORDER BY first_learned_at",
                progress_id
            )
        return [dict(r) for r in records]

    async def save_checkpoint(self, progress_id: int, checkpoint_data: dict) -> dict:
        """保存学习检查点"""
        import json
        now = datetime.now()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO learning_checkpoints (progress_id, checkpoint_data, created_at)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                progress_id, json.dumps(checkpoint_data), now
            )
        return dict(record)
```

**Step 4: Commit**

```bash
git add models/task.py storage/postgres.py
git commit -m "feat: add learning progress database schema and CRUD methods"
```

---

## Task 3: Telegram客户端核心

**Files:**
- Create: `bot/telegram_client.py`

**Step 1: 创建TelegramClient类**

```python
from telegram import Bot, Update
from telegram.constants import ParseMode
from typing import Optional, List
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger("pkos.telegram_client")

class TelegramClient:
    """Telegram Bot客户端 - 封装消息发送和格式化"""

    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.username = None

    async def initialize(self):
        """初始化bot，获取用户名"""
        me = await self.bot.get_me()
        self.username = me.username
        logger.info(f"Telegram bot initialized: @{self.username}")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: ParseMode = ParseMode.MARKDOWN,
        reply_to_message_id: Optional[int] = None
    ):
        """发送文本消息"""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id
            )
            logger.debug(f"Message sent to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # 如果Markdown解析失败，尝试纯文本
            if parse_mode == ParseMode.MARKDOWN:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=reply_to_message_id
                )

    async def send_long_message(self, chat_id: int, text: str, max_length: int = 4000):
        """发送长文本，自动分段"""
        if len(text) <= max_length:
            await self.send_message(chat_id, text)
            return

        # 按段落分割
        paragraphs = text.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_length:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    await self.send_message(chat_id, current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            await self.send_message(chat_id, current_chunk.strip())

    async def send_progress_message(self, chat_id: int, stage: str):
        """发送进度消息"""
        progress_messages = {
            "download": "⏳ 正在下载视频...",
            "transcribe": "🎤 正在转录音频...",
            "optimize": "🤖 正在优化内容...",
            "complete": "✅ 处理完成！"
        }
        message = progress_messages.get(stage, f"⏳ {stage}...")
        await self.send_message(chat_id, message)

# 全局Telegram客户端实例（将在main中初始化）
telegram_client: Optional[TelegramClient] = None

def get_telegram_client() -> TelegramClient:
    """获取全局Telegram客户端实例"""
    if telegram_client is None:
        raise RuntimeError("Telegram client not initialized")
    return telegram_client
```

**Step 2: Commit**

```bash
git add bot/telegram_client.py
git commit -m "feat: create TelegramClient with message sending utilities"
```

---

## Task 4: 会话管理器（工作区）

**Files:**
- Create: `bot/session_manager.py`

**Step 1: 创建SessionManager类**

```python
import redis.asyncio as redis
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger("pkos.session_manager")

class ConversationMode:
    """对话模式"""
    NORMAL = "normal"       # 普通对话模式
    LEARNING = "learning"   # 学习模式

class SessionManager:
    """会话管理器 - 管理用户的工作区上下文"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.session_ttl = 3600 * 24  # 24小时过期

    async def connect(self):
        """连接到Redis"""
        self.redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("SessionManager connected to Redis")

    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()

    def _get_key(self, user_id: str, key_type: str) -> str:
        """生成Redis key"""
        return f"telegram:user:{user_id}:{key_type}"

    async def get_workspace(self, user_id: str) -> List[str]:
        """获取用户的工作区文章列表"""
        key = self._get_key(user_id, "workspace")
        articles = await self.redis_client.lrange(key, 0, -1)
        return articles or []

    async def add_to_workspace(self, user_id: str, task_id: str) -> bool:
        """添加文章到工作区"""
        key = self._get_key(user_id, "workspace")

        # 检查是否已存在
        articles = await self.get_workspace(user_id)
        if task_id in articles:
            return False

        # 添加到列表末尾
        await self.redis_client.rpush(key, task_id)
        await self.redis_client.expire(key, self.session_ttl)
        logger.info(f"Added {task_id} to workspace for user {user_id}")
        return True

    async def remove_from_workspace(self, user_id: str, task_id: str) -> bool:
        """从工作区移除文章"""
        key = self._get_key(user_id, "workspace")
        removed_count = await self.redis_client.lrem(key, 0, task_id)
        return removed_count > 0

    async def clear_workspace(self, user_id: str):
        """清空工作区"""
        key = self._get_key(user_id, "workspace")
        await self.redis_client.delete(key)
        logger.info(f"Cleared workspace for user {user_id}")

    async def get_mode(self, user_id: str) -> str:
        """获取用户的对话模式"""
        key = self._get_key(user_id, "mode")
        mode = await self.redis_client.get(key)
        return mode or ConversationMode.NORMAL

    async def set_mode(self, user_id: str, mode: str):
        """设置用户的对话模式"""
        key = self._get_key(user_id, "mode")
        await self.redis_client.set(key, mode, ex=self.session_ttl)
        logger.info(f"Set mode to {mode} for user {user_id}")

    async def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取对话历史"""
        key = self._get_key(user_id, "history")
        history_json = await self.redis_client.lrange(key, -limit, -1)
        return [json.loads(h) for h in history_json]

    async def add_to_history(self, user_id: str, role: str, content: str):
        """添加到对话历史"""
        key = self._get_key(user_id, "history")
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        await self.redis_client.rpush(key, json.dumps(message))
        await self.redis_client.expire(key, self.session_ttl)

        # 限制历史记录长度（最多保留50条）
        await self.redis_client.ltrim(key, -50, -1)

    async def clear_history(self, user_id: str):
        """清空对话历史"""
        key = self._get_key(user_id, "history")
        await self.redis_client.delete(key)

    async def update_study_time(self, user_id: str, task_id: str, minutes: int):
        """更新学习时长（用于进度追踪）"""
        key = self._get_key(user_id, f"study_time:{task_id}")
        await self.redis_client.incrby(key, minutes)
        await self.redis_client.expire(key, self.session_ttl)

    async def get_study_time(self, user_id: str, task_id: str) -> int:
        """获取学习时长"""
        key = self._get_key(user_id, f"study_time:{task_id}")
        time = await self.redis_client.get(key)
        return int(time) if time else 0

# 全局会话管理器实例
session_manager = SessionManager()
```

**Step 2: Commit**

```bash
git add bot/session_manager.py
git commit -m "feat: add SessionManager for workspace and conversation state management"
```

---

## Task 5: 命令处理器

**Files:**
- Create: `bot/command_handlers.py`

**Step 1: 创建命令处理函数**

```python
from telegram import Update
from telegram.ext import ContextTypes
from bot.telegram_client import get_telegram_client
from bot.session_manager import session_manager, ConversationMode
from storage.postgres import storage
from config.logger import setup_logger

logger = setup_logger("pkos.command_handlers")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user_id = str(update.effective_user.id)

    welcome_message = """
👋 欢迎使用视频知识助手！

我可以帮你：
📹 处理抖音/B站视频链接，转录为文字
💬 与文章内容进行多轮对话
📚 学习模式：苏格拉底式引导学习
📊 追踪你的学习进度

**快速开始：**
直接发送视频链接即可开始处理

**常用命令：**
/history - 查看处理记录
/help - 查看完整帮助

让我们开始吧！
"""

    client = get_telegram_client()
    await client.send_message(update.effective_chat.id, welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    help_text = """
📖 **命令帮助**

━━━━━ 基础命令 ━━━━━
/start - 开始使用
/help - 查看帮助

━━━━━ 任务管理 ━━━━━
/history [n] - 查看最近n条记录（默认10）
/status <id> - 查询任务状态
/cancel <id> - 取消任务

━━━━━ 工作区管理 ━━━━━
/chat <id> - 激活文章（普通对话）
/learn <id> - 激活文章（学习模式）
/add <id> - 添加文章到工作区
/remove <id> - 移除文章
/context - 查看当前工作区
/clear - 清空工作区
/mode - 查看当前模式

━━━━━ 内容查看 ━━━━━
/original <id> - 查看原文
/outline <id> - 查看大纲
/summary <id> - 查看摘要

━━━━━ 深度分析 ━━━━━
/summarize - 总结工作区文章
/compare - 对比工作区文章
/synthesis - 综合分析
/extend - 延伸阅读建议
/qa - 提取问答

━━━━━ 学习进度 ━━━━━
/progress [id] - 查看学习进度
/checkpoint - 保存学习检查点
/review - 查看复习计划
/stats - 学习统计

💡 提示：激活工作区后，直接发送消息即可提问
"""

    client = get_telegram_client()
    await client.send_message(update.effective_chat.id, help_text)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /history 命令"""
    user_id = str(update.effective_user.id)

    # 获取参数（记录数量）
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
        limit = min(limit, 50)  # 最多50条

    await storage.connect()
    try:
        # 获取用户的任务列表（需要修改storage以支持按用户查询）
        # 暂时获取最近的任务
        tasks = await storage.get_recent_tasks(limit)

        if not tasks:
            response = "📝 暂无处理记录"
        else:
            response = f"📚 最近 {len(tasks)} 条记录：\n\n"
            for task in tasks:
                status_emoji = {
                    "processing": "⏳",
                    "completed": "✅",
                    "failed": "❌"
                }.get(task.status, "❓")

                response += f"{status_emoji} `{task.task_id[:8]}` - {task.title or '无标题'}\n"
                response += f"   平台: {task.platform} | {task.created_at.strftime('%m-%d %H:%M')}\n\n"
    finally:
        await storage.disconnect()

    client = get_telegram_client()
    await client.send_message(update.effective_chat.id, response)

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /chat 命令 - 激活普通对话模式"""
    user_id = str(update.effective_user.id)

    if not context.args:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 请提供任务ID\n用法: /chat <task_id>"
        )
        return

    task_id = context.args[0]

    await storage.connect()
    try:
        task = await storage.get_task(task_id)
        if not task:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                f"❌ 未找到任务: {task_id}"
            )
            return

        if task.status != "completed":
            await get_telegram_client().send_message(
                update.effective_chat.id,
                f"⚠️ 任务尚未完成，当前状态: {task.status}"
            )
            return

        # 清空工作区并添加新文章
        await session_manager.clear_workspace(user_id)
        await session_manager.add_to_workspace(user_id, task_id)
        await session_manager.set_mode(user_id, ConversationMode.NORMAL)
        await session_manager.clear_history(user_id)

        response = f"""
💬 已激活普通对话模式

📄 当前文章：《{task.title}》
📋 任务ID：`{task_id}`

现在可以直接提问，我会基于这篇文章回答。
使用 /learn {task_id} 切换到学习模式。
"""

        await get_telegram_client().send_message(update.effective_chat.id, response)

    finally:
        await storage.disconnect()

async def context_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /context 命令 - 查看工作区"""
    user_id = str(update.effective_user.id)

    workspace = await session_manager.get_workspace(user_id)
    mode = await session_manager.get_mode(user_id)

    if not workspace:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "📚 当前工作区为空\n使用 /chat <id> 或 /learn <id> 激活文章"
        )
        return

    await storage.connect()
    try:
        response = f"📚 当前工作区 ({mode} 模式)\n\n"

        for idx, task_id in enumerate(workspace, 1):
            task = await storage.get_task(task_id)
            if task:
                response += f"{idx}. `{task_id[:8]}` - {task.title or '无标题'}\n"

        response += f"\n共 {len(workspace)} 篇文章"

    finally:
        await storage.disconnect()

    await get_telegram_client().send_message(update.effective_chat.id, response)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /clear 命令 - 清空工作区"""
    user_id = str(update.effective_user.id)

    await session_manager.clear_workspace(user_id)
    await session_manager.clear_history(user_id)
    await session_manager.set_mode(user_id, ConversationMode.NORMAL)

    await get_telegram_client().send_message(
        update.effective_chat.id,
        "🗑️ 已清空工作区和对话历史"
    )

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /add 命令 - 添加文章到工作区"""
    user_id = str(update.effective_user.id)

    if not context.args:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 请提供任务ID\n用法: /add <task_id>"
        )
        return

    task_id = context.args[0]

    await storage.connect()
    try:
        task = await storage.get_task(task_id)
        if not task:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                f"❌ 未找到任务: {task_id}"
            )
            return

        if task.status != "completed":
            await get_telegram_client().send_message(
                update.effective_chat.id,
                f"⚠️ 任务尚未完成"
            )
            return

        added = await session_manager.add_to_workspace(user_id, task_id)

        if not added:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                "⚠️ 该文章已在工作区中"
            )
            return

        workspace = await session_manager.get_workspace(user_id)

        response = f"""
✅ 已添加文章到工作区

📄 《{task.title}》

📚 当前工作区：{len(workspace)} 篇文章
使用 /context 查看详情
"""

        await get_telegram_client().send_message(update.effective_chat.id, response)

    finally:
        await storage.disconnect()

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /mode 命令 - 查看当前模式"""
    user_id = str(update.effective_user.id)

    mode = await session_manager.get_mode(user_id)
    workspace = await session_manager.get_workspace(user_id)

    mode_name = "学习模式 📚" if mode == ConversationMode.LEARNING else "普通对话模式 💬"

    response = f"""
当前状态：

🎯 模式：{mode_name}
📚 工作区：{len(workspace)} 篇文章

使用 /context 查看工作区详情
"""

    await get_telegram_client().send_message(update.effective_chat.id, response)
```

**Step 2: 添加get_recent_tasks方法到storage**

在 `storage/postgres.py` 中添加：

```python
    async def get_recent_tasks(self, limit: int = 10) -> List[Task]:
        """获取最近的任务列表"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT * FROM tasks
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit
            )
        return [self._record_to_task(r) for r in records]
```

**Step 3: Commit**

```bash
git add bot/command_handlers.py storage/postgres.py
git commit -m "feat: add command handlers for basic bot interaction"
```

---

## Task 6: 消息路由和URL检测

**Files:**
- Create: `bot/message_handler.py`

**Step 1: 创建消息处理器**

```python
import re
import asyncio
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from bot.telegram_client import get_telegram_client
from bot.session_manager import session_manager, ConversationMode
from storage.postgres import storage
from processors.video_downloader import video_downloader
from processors.transcriber import transcriber
from processors.content_processor import content_processor
from models.task import TaskCreate
from config.logger import setup_logger

logger = setup_logger("pkos.message_handler")

class MessageHandler:
    """消息处理器 - 路由和处理用户消息"""

    @staticmethod
    def extract_video_url(text: str) -> str:
        """从文本中提取视频URL"""
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        return urls[0] if urls else ""

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户消息"""
        user_id = str(update.effective_user.id)
        chat_id = update.effective_chat.id
        text = update.message.text

        client = get_telegram_client()

        # 检查是否包含视频URL
        video_url = MessageHandler.extract_video_url(text)

        if video_url:
            # 处理视频链接
            await MessageHandler.handle_video_url(user_id, chat_id, video_url)
        else:
            # 检查工作区状态
            workspace = await session_manager.get_workspace(user_id)

            if not workspace:
                await client.send_message(
                    chat_id,
                    "💡 请先发送视频链接，或使用 /chat <task_id> 激活文章后再提问\n\n使用 /help 查看帮助"
                )
                return

            # 处理对话
            mode = await session_manager.get_mode(user_id)

            if mode == ConversationMode.LEARNING:
                await MessageHandler.handle_learning_conversation(user_id, chat_id, text, workspace)
            else:
                await MessageHandler.handle_normal_conversation(user_id, chat_id, text, workspace)

    @staticmethod
    async def handle_video_url(user_id: str, chat_id: int, video_url: str):
        """处理视频URL"""
        client = get_telegram_client()

        # 验证平台
        platform = video_downloader.detect_platform(video_url)
        if not platform:
            await client.send_message(
                chat_id,
                "❌ 目前仅支持抖音和B站视频"
            )
            return

        # 创建任务
        task_id = str(uuid.uuid4())

        await client.send_message(
            chat_id,
            f"📥 收到链接，正在处理...\n\n平台: {platform}\n任务ID: `{task_id[:8]}`"
        )

        # 异步处理视频
        asyncio.create_task(
            MessageHandler.process_video(user_id, chat_id, task_id, video_url, platform)
        )

    @staticmethod
    async def process_video(user_id: str, chat_id: int, task_id: str, video_url: str, platform: str):
        """异步处理视频"""
        client = get_telegram_client()

        try:
            await storage.connect()

            # 创建任务记录
            task = await storage.create_task(
                TaskCreate(task_id=task_id, video_url=video_url, platform=platform)
            )

            # 1. 下载视频
            await client.send_progress_message(chat_id, "download")
            audio_path, title = await video_downloader.download(video_url)

            # 2. 转录
            await client.send_progress_message(chat_id, "transcribe")
            raw_content = transcriber.transcribe(audio_path)

            # 3. 内容优化
            await client.send_progress_message(chat_id, "optimize")
            processed_content = await content_processor.process(raw_content, title)

            # 4. 更新任务状态
            await storage.update_task(
                task_id,
                title=title,
                status="completed",
                content=processed_content
            )

            # 5. 发送完成通知
            complete_message = f"""
✅ 处理完成！

📄 标题：《{title}》
📋 任务ID：`{task_id[:8]}`
📝 字数：{len(processed_content)}字

💡 快捷操作：
/outline {task_id[:8]} - 查看大纲
/summary {task_id[:8]} - 查看摘要
/chat {task_id[:8]} - 开始对话
/learn {task_id[:8]} - 学习模式
"""

            await client.send_message(chat_id, complete_message)

        except Exception as e:
            logger.error(f"Video processing failed: {e}", exc_info=True)
            await storage.update_task(task_id, status="failed", error_message=str(e))
            await client.send_message(
                chat_id,
                f"❌ 处理失败: {str(e)}"
            )
        finally:
            await storage.disconnect()

    @staticmethod
    async def handle_normal_conversation(user_id: str, chat_id: int, text: str, workspace: list):
        """处理普通对话"""
        from bot.conversation_engine import conversation_engine

        # 记录到历史
        await session_manager.add_to_history(user_id, "user", text)

        # 获取文章内容
        await storage.connect()
        try:
            articles_content = []
            for task_id in workspace:
                task = await storage.get_task(task_id)
                if task and task.content:
                    articles_content.append({
                        "task_id": task_id,
                        "title": task.title,
                        "content": task.content
                    })

            # 生成回答
            response = await conversation_engine.generate_response(
                user_id=user_id,
                question=text,
                articles=articles_content,
                mode=ConversationMode.NORMAL
            )

            # 记录助手回复
            await session_manager.add_to_history(user_id, "assistant", response)

            # 发送回复
            await get_telegram_client().send_long_message(chat_id, response)

        finally:
            await storage.disconnect()

    @staticmethod
    async def handle_learning_conversation(user_id: str, chat_id: int, text: str, workspace: list):
        """处理学习模式对话"""
        from bot.conversation_engine import conversation_engine

        # 记录到历史
        await session_manager.add_to_history(user_id, "user", text)

        # 获取文章内容和学习进度
        await storage.connect()
        try:
            articles_content = []
            for task_id in workspace:
                task = await storage.get_task(task_id)
                if task and task.content:
                    # 获取学习进度
                    progress = await storage.get_or_create_progress(user_id, task_id)

                    articles_content.append({
                        "task_id": task_id,
                        "title": task.title,
                        "content": task.content,
                        "progress": progress
                    })

            # 生成学习式回答
            response = await conversation_engine.generate_response(
                user_id=user_id,
                question=text,
                articles=articles_content,
                mode=ConversationMode.LEARNING
            )

            # 记录助手回复
            await session_manager.add_to_history(user_id, "assistant", response)

            # 更新学习进度（提问次数+1）
            for task_id in workspace:
                await storage.update_progress(
                    user_id, task_id,
                    questions_asked=await storage.get_or_create_progress(user_id, task_id).get("questions_asked", 0) + 1,
                    last_study_at=datetime.now()
                )

            # 发送回复
            await get_telegram_client().send_long_message(chat_id, response)

        finally:
            await storage.disconnect()

# 全局消息处理器
message_handler = MessageHandler()
```

**Step 2: Commit**

```bash
git add bot/message_handler.py
git commit -m "feat: add message handler with URL detection and conversation routing"
```

---

## Task 7: 对话引擎（LLM集成）

**Files:**
- Create: `bot/conversation_engine.py`

**Step 1: 创建ConversationEngine类**

```python
from typing import List, Dict, Any
from bot.session_manager import ConversationMode, session_manager
from processors.llm_client import llm_client
from config.logger import setup_logger

logger = setup_logger("pkos.conversation_engine")

LEARNING_MODE_PROMPT = """你是一位耐心的学习导师，使用苏格拉底式教学法。

当前学习内容：
{articles_info}

核心原则：
1. 先询问学习者已有知识，不要假设零基础
2. 通过问题引导思考，而非直接给答案
3. 解释清晰简洁（200-300字），使用类比和例子
4. 每次解释后必须验证理解（1-2个问题）
5. 根据回答调整教学策略
6. 庆祝正确理解，对错误给出友好反馈

响应结构：
- [解释/类比] (简洁，有例子)
- [理解检查问题] (开放式，引导思考)

语气：
- 友好、鼓励、非评判
- 像朋友交流，不是老师教训
- 适当使用emoji但不过度

对话历史：
{conversation_history}

学习者问题：{question}
"""

NORMAL_MODE_PROMPT = """你是一个高效的知识助手。

当前文章内容：
{articles_info}

原则：
1. 直接、准确地回答问题
2. 基于文章内容，不编造信息
3. 如果文章中没有相关信息，明确说明
4. 保持专业但友好的语气
5. 回答简洁明了，避免冗长

对话历史：
{conversation_history}

用户问题：{question}
"""

class ConversationEngine:
    """对话引擎 - 生成基于上下文的回答"""

    async def generate_response(
        self,
        user_id: str,
        question: str,
        articles: List[Dict[str, Any]],
        mode: str
    ) -> str:
        """生成回答"""

        # 构建文章信息
        articles_info = self._format_articles(articles)

        # 获取对话历史
        history = await session_manager.get_conversation_history(user_id, limit=5)
        conversation_history = self._format_history(history)

        # 选择提示词模板
        if mode == ConversationMode.LEARNING:
            system_prompt = LEARNING_MODE_PROMPT.format(
                articles_info=articles_info,
                conversation_history=conversation_history,
                question=question
            )
        else:
            system_prompt = NORMAL_MODE_PROMPT.format(
                articles_info=articles_info,
                conversation_history=conversation_history,
                question=question
            )

        # 调用LLM生成回答
        try:
            response = await llm_client.generate_chat_response(system_prompt, question)
            return response
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return "抱歉，我遇到了一些问题，无法生成回答。请稍后再试。"

    def _format_articles(self, articles: List[Dict[str, Any]]) -> str:
        """格式化文章信息"""
        if not articles:
            return "无"

        formatted = []
        for idx, article in enumerate(articles, 1):
            formatted.append(
                f"\n【文章{idx}】《{article['title']}》\n"
                f"任务ID: {article['task_id']}\n"
                f"内容摘要: {article['content'][:500]}...\n"
            )

        return "\n".join(formatted)

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """格式化对话历史"""
        if not history:
            return "（无历史记录）"

        formatted = []
        for msg in history[-5:]:  # 最近5轮
            role = "学习者" if msg["role"] == "user" else "助手"
            formatted.append(f"{role}: {msg['content']}")

        return "\n".join(formatted)

# 全局对话引擎
conversation_engine = ConversationEngine()
```

**Step 2: 在llm_client中添加通用chat方法**

在 `processors/llm_client.py` 中添加：

```python
    async def generate_chat_response(self, system_prompt: str, user_message: str) -> str:
        """生成对话回复"""
        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})

        if model_config.get("type") == "claude":
            response = await self.clients[model_name].messages.create(
                model=model_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            return response.content[0].text
        else:
            response = await self.clients[model_name].chat.completions.create(
                model=model_config.get("model", "gpt-4o"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content or "无法生成回复"
```

**Step 3: Commit**

```bash
git add bot/conversation_engine.py processors/llm_client.py
git commit -m "feat: add conversation engine with learning and normal modes"
```

---

## Task 8: 内容分析功能（outline/summary/qa/extend）

**Files:**
- Create: `bot/content_analysis.py`

**Step 1: 创建内容分析器**

```python
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from storage.postgres import storage
from processors.llm_client import llm_client
from bot.telegram_client import get_telegram_client
from config.logger import setup_logger

logger = setup_logger("pkos.content_analysis")

class ContentAnalyzer:
    """内容分析器 - 提供大纲、摘要、问答、延伸阅读等功能"""

    @staticmethod
    async def generate_outline(content: str, title: str) -> str:
        """生成文章大纲"""
        prompt = f"""请为以下文章生成结构化大纲。

文章标题：《{title}》

要求：
1. 提取主要章节和要点
2. 使用层级结构（一、二、三级标题）
3. 保持简洁，突出核心结构
4. 格式清晰易读

文章内容：
{content}
"""

        try:
            outline = await llm_client.generate_chat_response(
                "你是专业的内容分析师，擅长提取文章结构和要点。",
                prompt
            )
            return f"📋 《{title}》- 文章大纲\n\n{outline}"
        except Exception as e:
            logger.error(f"Failed to generate outline: {e}")
            return "❌ 生成大纲失败"

    @staticmethod
    async def generate_summary(content: str, title: str) -> str:
        """生成文章摘要"""
        prompt = f"""请为以下文章生成摘要。

文章标题：《{title}》

要求：
1. 提取核心观点（3-5个要点）
2. 总结关键论证逻辑
3. 包含重要数据或案例
4. 字数控制在300-500字

文章内容：
{content}
"""

        try:
            summary = await llm_client.generate_chat_response(
                "你是专业的内容总结专家，擅长提炼核心要点。",
                prompt
            )
            return f"📝 《{title}》- 摘要\n\n{summary}"
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return "❌ 生成摘要失败"

    @staticmethod
    async def generate_qa(content: str, title: str) -> str:
        """生成问答对"""
        prompt = f"""请从以下文章中提取5-8个核心问题和答案。

文章标题：《{title}》

要求：
1. 问题覆盖文章的关键知识点
2. 答案准确、简洁（每个答案50-100字）
3. 格式：Q1: ... / A1: ...
4. 问题由浅入深，循序渐进

文章内容：
{content}
"""

        try:
            qa = await llm_client.generate_chat_response(
                "你是专业的教学设计师，擅长设计高质量问答。",
                prompt
            )
            return f"❓《{title}》- 核心问答\n\n{qa}"
        except Exception as e:
            logger.error(f"Failed to generate Q&A: {e}")
            return "❌ 生成问答失败"

    @staticmethod
    async def generate_extensions(content: str, title: str) -> str:
        """生成延伸阅读建议"""
        prompt = f"""基于以下文章，推荐延伸阅读方向。

文章标题：《{title}》

要求：
1. 核心概念（3-5个关键术语）
2. 推荐学习方向（2-3个相关领域）
3. 实践工具或方法（2-3个）
4. 格式清晰，包含简短说明

文章内容：
{content[:1000]}...
"""

        try:
            extensions = await llm_client.generate_chat_response(
                "你是知识图谱专家，擅长构建知识间的关联。",
                prompt
            )
            return f"📚 《{title}》- 延伸阅读建议\n\n{extensions}"
        except Exception as e:
            logger.error(f"Failed to generate extensions: {e}")
            return "❌ 生成延伸阅读失败"

# 命令处理函数

async def outline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /outline 命令"""
    if not context.args:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 请提供任务ID\n用法: /outline <task_id>"
        )
        return

    task_id = context.args[0]

    await storage.connect()
    try:
        task = await storage.get_task(task_id)
        if not task or not task.content:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                f"❌ 未找到任务或内容不完整: {task_id}"
            )
            return

        # 发送"生成中"提示
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "⏳ 正在生成大纲..."
        )

        outline = await ContentAnalyzer.generate_outline(task.content, task.title)
        await get_telegram_client().send_long_message(update.effective_chat.id, outline)

    finally:
        await storage.disconnect()

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /summary 命令"""
    if not context.args:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 请提供任务ID\n用法: /summary <task_id>"
        )
        return

    task_id = context.args[0]

    await storage.connect()
    try:
        task = await storage.get_task(task_id)
        if not task or not task.content:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                f"❌ 未找到任务或内容不完整: {task_id}"
            )
            return

        await get_telegram_client().send_message(
            update.effective_chat.id,
            "⏳ 正在生成摘要..."
        )

        summary = await ContentAnalyzer.generate_summary(task.content, task.title)
        await get_telegram_client().send_long_message(update.effective_chat.id, summary)

    finally:
        await storage.disconnect()

async def qa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /qa 命令"""
    user_id = str(update.effective_user.id)
    from bot.session_manager import session_manager

    workspace = await session_manager.get_workspace(user_id)

    if not workspace:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 工作区为空\n使用 /chat <id> 激活文章后再使用此命令"
        )
        return

    await storage.connect()
    try:
        task_id = workspace[0]  # 使用工作区第一篇文章
        task = await storage.get_task(task_id)

        if not task or not task.content:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                "❌ 文章内容不完整"
            )
            return

        await get_telegram_client().send_message(
            update.effective_chat.id,
            "⏳ 正在生成问答..."
        )

        qa = await ContentAnalyzer.generate_qa(task.content, task.title)
        await get_telegram_client().send_long_message(update.effective_chat.id, qa)

    finally:
        await storage.disconnect()

async def extend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /extend 命令"""
    user_id = str(update.effective_user.id)
    from bot.session_manager import session_manager

    workspace = await session_manager.get_workspace(user_id)

    if not workspace:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 工作区为空\n使用 /chat <id> 激活文章后再使用此命令"
        )
        return

    await storage.connect()
    try:
        task_id = workspace[0]
        task = await storage.get_task(task_id)

        if not task or not task.content:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                "❌ 文章内容不完整"
            )
            return

        await get_telegram_client().send_message(
            update.effective_chat.id,
            "⏳ 正在生成延伸阅读建议..."
        )

        extensions = await ContentAnalyzer.generate_extensions(task.content, task.title)
        await get_telegram_client().send_long_message(update.effective_chat.id, extensions)

    finally:
        await storage.disconnect()
```

**Step 2: Commit**

```bash
git add bot/content_analysis.py
git commit -m "feat: add content analysis features (outline/summary/qa/extend)"
```

---

## Task 9: 进度追踪功能

**Files:**
- Create: `bot/progress_tracker.py`

**Step 1: 创建进度追踪器**

```python
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from storage.postgres import storage
from bot.telegram_client import get_telegram_client
from bot.session_manager import session_manager
from config.logger import setup_logger

logger = setup_logger("pkos.progress_tracker")

async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /progress 命令"""
    user_id = str(update.effective_user.id)

    # 如果提供了task_id，显示单个任务进度
    if context.args:
        task_id = context.args[0]
        await show_task_progress(update.effective_chat.id, user_id, task_id)
    else:
        # 否则显示工作区所有任务的进度
        await show_workspace_progress(update.effective_chat.id, user_id)

async def show_task_progress(chat_id: int, user_id: str, task_id: str):
    """显示单个任务的学习进度"""
    await storage.connect()
    try:
        task = await storage.get_task(task_id)
        if not task:
            await get_telegram_client().send_message(chat_id, f"❌ 未找到任务: {task_id}")
            return

        progress = await storage.get_or_create_progress(user_id, task_id)

        # 获取概念列表
        concepts = await storage.get_concepts_by_progress(progress["id"])

        # 格式化进度条
        mastery = progress.get("mastery_level", 0)
        bar_length = 20
        filled = int(bar_length * mastery / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        response = f"""📊 《{task.title}》学习进度

━━━━━━━━━━━━━━━━━━━━
进度：{bar} {mastery}%
━━━━━━━━━━━━━━━━━━━━

📅 学习信息：
• 开始时间：{progress.get('started_at') or '未开始'}
• 最近学习：{progress.get('last_study_at') or '未开始'}
• 累计时长：{progress.get('total_study_time', 0)}分钟
• 提问次数：{progress.get('questions_asked', 0)}次

"""

        # 添加概念掌握情况
        if concepts:
            mastered = [c for c in concepts if c["status"] == "mastered"]
            learning = [c for c in concepts if c["status"] == "understanding"]
            struggling = [c for c in concepts if c["status"] == "struggling"]

            response += f"\n✅ 已掌握概念 ({len(mastered)})：\n"
            for c in mastered[:5]:
                response += f"  • {c['concept_name']}\n"

            if learning:
                response += f"\n🔄 学习中概念 ({len(learning)})：\n"
                for c in learning[:3]:
                    response += f"  • {c['concept_name']}\n"

            if struggling:
                response += f"\n⚠️ 困难概念 ({len(struggling)})：\n"
                for c in struggling[:3]:
                    response += f"  • {c['concept_name']}\n"

        response += "\n💡 使用 /learn {} 继续学习".format(task_id[:8])

        await get_telegram_client().send_message(chat_id, response)

    finally:
        await storage.disconnect()

async def show_workspace_progress(chat_id: int, user_id: str):
    """显示工作区所有任务的进度"""
    workspace = await session_manager.get_workspace(user_id)

    if not workspace:
        await get_telegram_client().send_message(
            chat_id,
            "📚 工作区为空\n使用 /chat <id> 或 /learn <id> 激活文章"
        )
        return

    await storage.connect()
    try:
        response = "📚 工作区学习进度总览\n\n"

        total_mastery = 0
        total_time = 0

        for idx, task_id in enumerate(workspace, 1):
            task = await storage.get_task(task_id)
            if not task:
                continue

            progress = await storage.get_or_create_progress(user_id, task_id)
            mastery = progress.get("mastery_level", 0)
            study_time = progress.get("total_study_time", 0)

            total_mastery += mastery
            total_time += study_time

            # 进度条（10格）
            filled = int(10 * mastery / 100)
            bar = "█" * filled + "░" * (10 - filled)

            response += f"{idx}️⃣ 《{task.title}》\n"
            response += f"   进度：{bar} {mastery}%\n"
            response += f"   时长：{study_time}分钟\n\n"

        # 总体统计
        avg_mastery = total_mastery // len(workspace) if workspace else 0
        response += f"━━━━━━━━━━━━━━━━━━━━\n"
        response += f"📊 总体统计：\n"
        response += f"• 平均进度：{avg_mastery}%\n"
        response += f"• 累计学时：{total_time}分钟\n"

        await get_telegram_client().send_message(chat_id, response)

    finally:
        await storage.disconnect()

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /stats 命令 - 显示学习统计"""
    user_id = str(update.effective_user.id)

    await storage.connect()
    try:
        # 获取用户所有学习进度
        all_progress = await storage.get_user_progress_list(user_id, limit=100)

        if not all_progress:
            await get_telegram_client().send_message(
                update.effective_chat.id,
                "📈 暂无学习记录\n开始学习后即可查看统计"
            )
            return

        # 统计数据
        total_articles = len(all_progress)
        learning_count = sum(1 for p in all_progress if p["status"] == "learning")
        mastered_count = sum(1 for p in all_progress if p["status"] == "mastered")
        total_time = sum(p.get("total_study_time", 0) for p in all_progress)
        total_questions = sum(p.get("questions_asked", 0) for p in all_progress)
        avg_mastery = sum(p.get("mastery_level", 0) for p in all_progress) // total_articles if total_articles else 0

        # 计算学习天数
        started_dates = [p["started_at"] for p in all_progress if p.get("started_at")]
        study_days = len(set(d.date() for d in started_dates)) if started_dates else 0

        response = f"""📈 你的学习统计

━━━━━━━━━━━━━━━━━━━━
🎓 总体概况
━━━━━━━━━━━━━━━━━━━━
• 学习天数：{study_days}天
• 累计学时：{total_time}分钟
• 日均学习：{total_time // study_days if study_days else 0}分钟

━━━━━━━━━━━━━━━━━━━━
📚 文章进度
━━━━━━━━━━━━━━━━━━━━
• 处理文章数：{total_articles}篇
• 学习中：{learning_count}篇
• 已掌握：{mastered_count}篇

━━━━━━━━━━━━━━━━━━━━
🧠 知识掌握
━━━━━━━━━━━━━━━━━━━━
• 平均掌握度：{avg_mastery}%
• 提问次数：{total_questions}次

💡 继续保持学习习惯！
"""

        await get_telegram_client().send_message(update.effective_chat.id, response)

    finally:
        await storage.disconnect()

async def checkpoint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /checkpoint 命令 - 保存学习检查点"""
    user_id = str(update.effective_user.id)

    workspace = await session_manager.get_workspace(user_id)

    if not workspace:
        await get_telegram_client().send_message(
            update.effective_chat.id,
            "❌ 工作区为空，无法保存检查点"
        )
        return

    await storage.connect()
    try:
        for task_id in workspace:
            progress = await storage.get_or_create_progress(user_id, task_id)

            # 保存检查点
            checkpoint_data = {
                "mastery_level": progress.get("mastery_level", 0),
                "questions_asked": progress.get("questions_asked", 0),
                "total_study_time": progress.get("total_study_time", 0),
                "timestamp": datetime.now().isoformat()
            }

            await storage.save_checkpoint(progress["id"], checkpoint_data)

        await get_telegram_client().send_message(
            update.effective_chat.id,
            f"💾 学习进度已保存\n\n保存了 {len(workspace)} 篇文章的检查点"
        )

    finally:
        await storage.disconnect()
```

**Step 2: Commit**

```bash
git add bot/progress_tracker.py
git commit -m "feat: add learning progress tracking and statistics"
```

---

## Task 10: 主程序入口和启动脚本

**Files:**
- Create: `bot/telegram_main.py`

**Step 1: 创建Telegram bot主程序**

```python
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.telegram_client import TelegramClient, telegram_client
from bot import command_handlers
from bot.message_handler import message_handler
from bot.content_analysis import outline_command, summary_command, qa_command, extend_command
from bot.progress_tracker import progress_command, stats_command, checkpoint_command
from bot.session_manager import session_manager
from storage.postgres import storage
from config.settings import settings
from config.logger import logger

async def post_init(application: Application):
    """应用初始化后的回调"""
    # 初始化Telegram客户端
    global telegram_client
    telegram_client = TelegramClient(settings.telegram_bot_token)
    await telegram_client.initialize()

    # 连接数据库
    await storage.connect()

    # 连接Redis
    await session_manager.connect()

    logger.info("✅ Telegram bot initialized successfully")

async def post_shutdown(application: Application):
    """应用关闭时的回调"""
    await storage.disconnect()
    await session_manager.disconnect()
    logger.info("Telegram bot shutdown")

def main():
    """主函数"""
    # 创建Application
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # 注册命令处理器
    application.add_handler(CommandHandler("start", command_handlers.start_command))
    application.add_handler(CommandHandler("help", command_handlers.help_command))
    application.add_handler(CommandHandler("history", command_handlers.history_command))
    application.add_handler(CommandHandler("chat", command_handlers.chat_command))
    application.add_handler(CommandHandler("context", command_handlers.context_command))
    application.add_handler(CommandHandler("clear", command_handlers.clear_command))
    application.add_handler(CommandHandler("add", command_handlers.add_command))
    application.add_handler(CommandHandler("mode", command_handlers.mode_command))

    # 内容分析命令
    application.add_handler(CommandHandler("outline", outline_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("qa", qa_command))
    application.add_handler(CommandHandler("extend", extend_command))

    # 进度追踪命令
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("checkpoint", checkpoint_command))

    # 消息处理器（处理所有非命令消息）
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.handle_message)
    )

    # 启动bot（Long Polling模式）
    logger.info("🚀 Starting Telegram bot in Long Polling mode...")
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
```

**Step 2: 更新配置文件**

在 `config/settings.py` 中添加Telegram配置：

```python
    # 在Settings类中添加
    telegram_bot_token: str
    telegram_bot_username: Optional[str] = None
```

**Step 3: 创建启动脚本**

创建 `start_telegram_bot.py`:

```python
#!/usr/bin/env python3
"""Telegram Bot启动脚本"""

if __name__ == "__main__":
    from bot.telegram_main import main
    main()
```

**Step 4: 添加执行权限**

Run: `chmod +x start_telegram_bot.py`

**Step 5: Commit**

```bash
git add bot/telegram_main.py config/settings.py start_telegram_bot.py
git commit -m "feat: add telegram bot main entry and startup script"
```

---

## Task 11: 测试和调试

**Files:**
- Create: `tests/test_telegram_integration.py`

**Step 1: 创建基础测试**

```python
import pytest
from bot.telegram_client import TelegramClient
from bot.session_manager import SessionManager

@pytest.mark.asyncio
async def test_session_manager():
    """测试会话管理器"""
    sm = SessionManager()
    await sm.connect()

    user_id = "test_user_123"

    # 测试工作区操作
    await sm.add_to_workspace(user_id, "task_1")
    workspace = await sm.get_workspace(user_id)
    assert "task_1" in workspace

    await sm.clear_workspace(user_id)
    workspace = await sm.get_workspace(user_id)
    assert len(workspace) == 0

    await sm.disconnect()

@pytest.mark.asyncio
async def test_message_handler():
    """测试URL提取"""
    from bot.message_handler import MessageHandler

    text1 = "请帮我处理这个视频 https://www.bilibili.com/video/BV1xx"
    url1 = MessageHandler.extract_video_url(text1)
    assert "bilibili.com" in url1

    text2 = "这是一段没有链接的文字"
    url2 = MessageHandler.extract_video_url(text2)
    assert url2 == ""
```

**Step 2: 手动测试清单**

创建 `docs/testing-telegram-bot.md`:

```markdown
# Telegram Bot 测试清单

## 基础功能测试

- [ ] /start 命令 - 显示欢迎消息
- [ ] /help 命令 - 显示帮助信息
- [ ] 发送视频链接 - 触发处理流程
- [ ] /history 命令 - 查看历史记录

## 工作区管理测试

- [ ] /chat <id> - 激活文章
- [ ] /add <id> - 添加文章到工作区
- [ ] /context - 查看工作区
- [ ] /clear - 清空工作区
- [ ] /mode - 查看当前模式

## 对话功能测试

- [ ] 普通对话模式 - 直接回答问题
- [ ] 学习模式 - 苏格拉底式引导
- [ ] 多轮对话 - 上下文保持
- [ ] 多文章对话 - 综合分析

## 内容分析测试

- [ ] /outline - 生成大纲
- [ ] /summary - 生成摘要
- [ ] /qa - 生成问答
- [ ] /extend - 延伸阅读

## 进度追踪测试

- [ ] /progress - 查看进度
- [ ] /stats - 学习统计
- [ ] /checkpoint - 保存检查点

## 错误处理测试

- [ ] 无效的task_id
- [ ] 空工作区操作
- [ ] LLM调用失败
- [ ] 网络超时
```

**Step 3: 运行测试**

Run: `pytest tests/test_telegram_integration.py -v`

**Step 4: Commit**

```bash
git add tests/test_telegram_integration.py docs/testing-telegram-bot.md
git commit -m "test: add telegram bot integration tests and manual testing guide"
```

---

## Task 12: 文档和部署指南

**Files:**
- Update: `README.md`
- Create: `docs/telegram-bot-guide.md`

**Step 1: 创建Telegram Bot使用指南**

创建 `docs/telegram-bot-guide.md`:

```markdown
# Telegram Bot 使用指南

## 快速开始

### 1. 获取Bot Token

1. 在Telegram中找到 @BotFather
2. 发送 `/newbot` 创建新bot
3. 按提示设置bot名称和用户名
4. 获得bot token（格式：`123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`）

### 2. 配置环境

编辑 `.env` 文件：

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动bot

```bash
python start_telegram_bot.py
```

## 功能说明

### 视频处理

直接发送视频链接即可：
- 支持B站: https://www.bilibili.com/video/BVxxx
- 支持抖音: https://v.douyin.com/xxx

### 工作区管理

激活文章后可以进行对话：

```
/chat task_abc123    # 普通对话模式
/learn task_abc123   # 学习模式
/add task_xyz456     # 添加更多文章
/context             # 查看当前工作区
```

### 对话模式

**普通模式**：直接回答问题，高效简洁

**学习模式**：
- 苏格拉底式提问
- 引导式思考
- 理解验证
- 循序渐进

### 内容分析

```
/outline task_id   # 结构化大纲
/summary task_id   # 核心摘要
/qa                # 问答对（需先激活工作区）
/extend            # 延伸阅读建议
```

### 学习进度

```
/progress          # 查看工作区进度
/progress task_id  # 查看单个任务进度
/stats             # 学习统计
/checkpoint        # 保存当前进度
```

## 使用场景

### 场景1：快速提取视频要点

1. 发送视频链接
2. 等待处理完成
3. `/summary task_id` 查看摘要
4. `/outline task_id` 查看结构

### 场景2：深度学习某个主题

1. `/learn task_id` 进入学习模式
2. 与bot对话，bot会引导你思考
3. 定期 `/checkpoint` 保存进度
4. `/progress` 查看掌握情况

### 场景3：对比多个视频观点

1. 处理多个相关视频
2. `/chat task_1` 激活第一个
3. `/add task_2` 添加第二个
4. 提问：「对比这两个视频的核心观点」

## 最佳实践

1. **定期保存进度**：使用 `/checkpoint`
2. **善用学习模式**：复杂概念用 `/learn`
3. **多文章分析**：相关主题放入同一工作区
4. **查看统计**：定期 `/stats` 了解学习情况

## 故障排除

### Bot无响应

- 检查bot是否在运行
- 检查网络连接
- 查看日志：`tail -f logs/telegram_bot.log`

### 处理失败

- 检查视频链接是否有效
- 抖音需要cookies文件
- 查看 `/status task_id` 了解详情

### Redis连接失败

```bash
# 启动Redis
redis-server

# 检查连接
redis-cli ping
```
```

**Step 2: 更新主README**

在 `README.md` 中添加Telegram Bot部分：

```markdown
## Telegram Bot

PKOS现已支持Telegram Bot接口，提供更便捷的交互体验。

### 特性

- 📹 直接发送视频链接即可处理
- 💬 多轮对话，支持上下文记忆
- 📚 学习模式，苏格拉底式引导学习
- 📊 学习进度追踪和统计
- 🔍 大纲、摘要、问答自动生成

### 快速开始

```bash
# 配置bot token
echo "TELEGRAM_BOT_TOKEN=your_token" >> .env

# 启动bot
python start_telegram_bot.py
```

详细文档：[Telegram Bot使用指南](docs/telegram-bot-guide.md)
```

**Step 3: Commit**

```bash
git add docs/telegram-bot-guide.md README.md
git commit -m "docs: add telegram bot user guide and update README"
```

---

## 实施完成

所有12个任务已完成规划。接下来选择执行方式：

### 选项1: 子代理驱动（当前会话）

使用 `superpowers:subagent-driven-development` 在当前会话中执行：
- 每个任务派发一个新的子代理
- 任务间进行代码审查
- 快速迭代

### 选项2: 并行会话（独立会话）

打开新会话并使用 `superpowers:executing-plans`：
- 批量执行所有任务
- 在关键检查点暂停审查
- 适合长时间运行

**你选择哪种执行方式？**