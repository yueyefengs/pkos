"""
Telegram Bot API客户端封装
提供消息发送、长文本分割等基础功能
"""
from telegram import Bot
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from typing import Optional
import os
from config.settings import settings
from config.logger import logger

class TelegramClient:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.max_message_length = 4096  # Telegram限制

    async def initialize(self):
        """初始化Bot实例"""
        # 配置代理（从环境变量读取）
        proxy_url = os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')

        if proxy_url:
            logger.info(f"Using proxy: {proxy_url}")
            # 创建带代理的请求对象
            # 注意：参数名是 proxy，不是 proxy_url
            request = HTTPXRequest(
                proxy=proxy_url,
                connect_timeout=30.0,
                read_timeout=30.0,
                write_timeout=30.0
            )
            self.bot = Bot(token=settings.telegram_bot_token, request=request)
        else:
            logger.info("No proxy configured, connecting directly")
            self.bot = Bot(token=settings.telegram_bot_token)

        logger.info(f"Telegram bot initialized: {settings.telegram_bot_username}")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        disable_web_page_preview: bool = True
    ) -> None:
        """发送消息"""
        if not self.bot:
            raise RuntimeError("Bot not initialized. Call initialize() first.")

        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            logger.debug(f"Message sent to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            raise

    async def send_long_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        disable_web_page_preview: bool = True
    ) -> None:
        """
        发送长消息(自动分割)
        如果消息超过Telegram限制,自动分段发送
        """
        if len(text) <= self.max_message_length:
            await self.send_message(chat_id, text, parse_mode, disable_web_page_preview)
            return

        # 按换行符分割
        lines = text.split('\n')
        current_chunk = ""

        for line in lines:
            # 如果单行就超长,强制截断
            if len(line) > self.max_message_length:
                if current_chunk:
                    await self.send_message(chat_id, current_chunk, parse_mode, disable_web_page_preview)
                    current_chunk = ""

                # 分段发送超长行
                for i in range(0, len(line), self.max_message_length):
                    chunk = line[i:i + self.max_message_length]
                    await self.send_message(chat_id, chunk, parse_mode, disable_web_page_preview)
                continue

            # 检查添加这行会不会超长
            if len(current_chunk) + len(line) + 1 > self.max_message_length:
                await self.send_message(chat_id, current_chunk, parse_mode, disable_web_page_preview)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line

        # 发送剩余部分
        if current_chunk:
            await self.send_message(chat_id, current_chunk, parse_mode, disable_web_page_preview)

    async def send_progress_message(
        self,
        chat_id: str,
        stage: str,
        message: str
    ) -> None:
        """
        发送处理进度消息

        Args:
            chat_id: 聊天ID
            stage: 处理阶段(downloading/transcribing/processing)
            message: 进度消息
        """
        emoji_map = {
            "downloading": "⬇️",
            "transcribing": "🎤",
            "processing": "🤖",
            "completed": "✅",
            "failed": "❌"
        }

        emoji = emoji_map.get(stage, "ℹ️")
        # 转义 Markdown 特殊字符，避免解析错误
        escaped_message = self._escape_markdown(message)
        full_message = f"{emoji} **{stage.upper()}**\n{escaped_message}"

        await self.send_message(chat_id, full_message)

    def _escape_markdown(self, text: str) -> str:
        """
        转义 Telegram Markdown 特殊字符

        Args:
            text: 原始文本

        Returns:
            转义后的文本
        """
        return escape_markdown_v2(text)


def escape_markdown_v2(text: str) -> str:
    """
    转义 Telegram Markdown V2 特殊字符（公共函数）

    Args:
        text: 原始文本

    Returns:
        转义后的文本
    """
    if not text:
        return ""
    # Telegram Markdown 特殊字符
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


# 全局客户端实例
_telegram_client: Optional[TelegramClient] = None

def get_telegram_client() -> TelegramClient:
    """获取全局Telegram客户端实例"""
    global _telegram_client
    if _telegram_client is None:
        _telegram_client = TelegramClient()
    return _telegram_client
