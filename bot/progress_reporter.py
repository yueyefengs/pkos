"""
进度上报器
持有 Telegram 消息 ID，提供 sync/async 两种更新接口，内置限流
"""
import asyncio
import time

from config.logger import logger


class ProgressReporter:
    """统一管理进度消息的编辑，内置 2 秒限流避免触发 Telegram 频率限制"""

    MIN_INTERVAL = 2.0

    def __init__(self, client, chat_id: str, message_id: int, loop: asyncio.AbstractEventLoop):
        self._client = client
        self._chat_id = chat_id
        self._message_id = message_id
        self._loop = loop
        self._last_update = 0.0

    def sync_update(self, stage: str, text: str):
        """从同步/线程上下文调用（yt-dlp progress_hook、whisper segment 循环）"""
        now = time.monotonic()
        if now - self._last_update < self.MIN_INTERVAL:
            return
        self._last_update = now
        future = asyncio.run_coroutine_threadsafe(
            self._client.edit_progress_message(self._chat_id, self._message_id, stage, text),
            self._loop,
        )
        # 非阻塞：不等待结果，失败静默忽略（edit_progress_message 内部已 catch）
        future.add_done_callback(lambda f: f.exception())

    async def async_update(self, stage: str, text: str):
        """从 async 代码调用（LLM 处理阶段）"""
        self._last_update = time.monotonic()
        await self._client.edit_progress_message(self._chat_id, self._message_id, stage, text)
