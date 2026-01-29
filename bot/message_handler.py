"""
Telegram Bot消息处理器
负责消息路由: URL检测 -> 视频处理 或 对话引擎
"""
import re
import uuid
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from bot.session_manager import get_session_manager
from bot.telegram_client import get_telegram_client
from processors.video_downloader import video_downloader
from processors.transcriber import transcriber
from processors.content_processor import content_processor
from storage.postgres import storage
from models.task import TaskCreate
from config.logger import logger


class MessageHandler:
    """消息处理器"""

    @staticmethod
    def extract_video_url(text: str) -> str:
        """从文本中提取视频URL"""
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        return urls[0] if urls else ""

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        处理普通文本消息
        1. 检测是否为视频URL -> 启动视频处理流程
        2. 否则检查工作区 -> 路由到对话引擎
        3. 工作区为空 -> 提示用户
        """
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        text = update.message.text
        client = get_telegram_client()
        session = get_session_manager()

        # 1. 检测视频URL
        video_url = MessageHandler.extract_video_url(text)
        if video_url:
            await MessageHandler.handle_video_url(chat_id, user_id, video_url)
            return

        # 2. 检查工作区状态
        await session.connect()
        workspace_ids = await session.get_workspace(user_id)
        await session.disconnect()

        if not workspace_ids:
            await client.send_message(
                chat_id,
                "📭 工作区为空\n\n"
                "请先:\n"
                "1️⃣ 发送视频链接处理内容\n"
                "2️⃣ 使用 `/chat [任务ID]` 激活已有文章\n"
                "3️⃣ 使用 `/history` 查看历史记录"
            )
            return

        # 3. 路由到对话引擎
        # 这里会在Task 7实现
        from bot.conversation_engine import ConversationEngine
        await ConversationEngine.handle_conversation(update, context)

    @staticmethod
    async def handle_video_url(chat_id: str, user_id: str, video_url: str):
        """
        处理视频URL
        1. 验证平台
        2. 创建任务
        3. 异步处理视频
        """
        client = get_telegram_client()

        # 验证平台
        platform = video_downloader.detect_platform(video_url)
        if not platform:
            await client.send_message(
                chat_id,
                "❌ 不支持的视频平台\n"
                "目前仅支持: 抖音、B站"
            )
            return

        # 创建任务
        task_id = str(uuid.uuid4())

        try:
            await storage.connect()
            task = await storage.create_task(
                TaskCreate(task_id=task_id, video_url=video_url, platform=platform)
            )
            await storage.disconnect()

            await client.send_message(
                chat_id,
                f"✅ 收到链接,开始处理...\n\n"
                f"平台: {platform}\n"
                f"任务ID: `{task.id}`\n\n"
                f"处理完成后使用 `/chat {task.id}` 激活对话"
            )

            # 异步处理视频
            asyncio.create_task(
                MessageHandler.process_video(chat_id, user_id, task.id, task_id, video_url)
            )

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            await client.send_message(
                chat_id,
                f"❌ 创建任务失败: {str(e)}"
            )

    @staticmethod
    async def process_video(
        chat_id: str,
        user_id: str,
        db_task_id: int,
        task_id: str,
        video_url: str
    ):
        """
        异步处理视频任务
        流程: 下载 -> 转录 -> 内容处理
        """
        client = get_telegram_client()

        try:
            await storage.connect()

            # 1. 下载视频
            await client.send_progress_message(chat_id, "downloading", "正在下载视频...")
            audio_path, title = await video_downloader.download(video_url)
            logger.info(f"Downloaded video: {title}")

            # 2. 转录音频
            await client.send_progress_message(chat_id, "transcribing", "正在转录音频...")
            raw_content = transcriber.transcribe(audio_path)
            logger.info(f"Transcribed audio for task {task_id}")

            # 3. 内容处理(优化文本)
            await client.send_progress_message(chat_id, "processing", "正在优化内容...")
            processed_content = await content_processor.process(raw_content, title)
            logger.info(f"Processed content for task {task_id}")

            # 4. 更新任务状态
            await storage.update_task(
                task_id,
                title=title,
                status="completed",
                content=processed_content
            )

            # 5. 发送完成通知
            await client.send_progress_message(
                chat_id,
                "completed",
                f"✅ 处理完成!\n\n"
                f"**标题:** {title}\n"
                f"**任务ID:** `{db_task_id}`\n\n"
                f"使用 `/chat {db_task_id}` 开始对话\n"
                f"或使用 `/learn {db_task_id}` 进入学习模式"
            )

            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Failed to process video {task_id}: {e}")

            # 更新任务为失败状态
            await storage.update_task(task_id, status="failed", error_message=str(e))

            await client.send_progress_message(
                chat_id,
                "failed",
                f"处理失败: {str(e)}"
            )

        finally:
            await storage.disconnect()


# 导出处理函数供主程序使用
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """消息处理入口"""
    await MessageHandler.handle_message(update, context)
