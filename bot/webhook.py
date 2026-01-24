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
