import asyncio
import uuid
import json
from typing import Dict, Any
from bot.feishu_client import feishu_client
from storage.postgres import storage
from processors.video_downloader import video_downloader
from processors.transcriber import transcriber
from processors.content_processor import content_processor
from models.task import TaskCreate

class WebhookHandler:
    def handle_message_receive(self, data) -> None:
        """处理飞书消息事件 - SDK自动解析"""
        from config.settings import settings
        event = data.event
        message = event.message
        sender = event.sender

        # 群聊@检测
        if message.chat_type == "group":
            mentions = message.mentions
            if not mentions or not any(m.id.user_id == settings.feishu_app_id for m in mentions):
                return

        # 提取消息内容
        content_dict = json.loads(message.content)
        text = content_dict.get("text", "")
        sender_id = sender.sender_id.open_id

        # 提取视频URL
        video_url = self._extract_video_url(text)
        if not video_url:
            feishu_client.send_message(
                sender_id,
                content="请发送有效的抖音或B站视频链接"
            )
            return

        # 验证平台
        platform = video_downloader.detect_platform(video_url)
        if not platform:
            feishu_client.send_message(
                sender_id,
                content="目前仅支持抖音和B站视频"
            )
            return

        # 创建任务并异步处理视频
        asyncio.create_task(self._handle_video_task(video_url, platform, sender_id))

    async def _handle_video_task(self, video_url: str, platform: str, sender_id: str):
        """创建任务并开始处理视频"""
        task_id = str(uuid.uuid4())
        await storage.connect()
        task = await storage.create_task(
            TaskCreate(task_id=task_id, video_url=video_url, platform=platform)
        )
        await storage.disconnect()

        # 回复用户
        feishu_client.send_message(
            sender_id,
            content=f"收到链接，正在处理中...\n平台: {platform}\n任务ID: {task_id[:8]}"
        )

        # 异步处理视频
        await self._process_video(task_id, video_url, sender_id)

    async def _process_video(self, task_id: str, video_url: str, user_id: str):
        """异步处理视频"""
        try:
            await storage.connect()

            # 1. 下载视频
            feishu_client.send_message(user_id, content="正在下载视频...")
            audio_path, title = await video_downloader.download(video_url)

            # 2. 转录
            feishu_client.send_message(user_id, content="正在转录音频...")
            raw_content = transcriber.transcribe(audio_path)

            # 3. 内容处理
            feishu_client.send_message(user_id, content="正在优化内容...")
            processed_content = await content_processor.process(raw_content, title)

            # 4. 保存到多维表格
            feishu_client.send_message(user_id, content="正在保存到知识库...")
            record_id = feishu_client.create_record(title, video_url, processed_content)

            # 5. 更新任务状态
            await storage.update_task(
                task_id,
                title=title,
                status="completed",
                content=processed_content
            )

            # 6. 发送完成通知
            feishu_client.send_message(
                user_id,
                content=f"处理完成！\n\n标题: {title}\n已保存到多维表格"
            )

        except Exception as e:
            await storage.update_task(task_id, status="failed", error_message=str(e))
            feishu_client.send_message(
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
