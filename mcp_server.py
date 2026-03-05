#!/usr/bin/env python3
"""
PKOS MCP Server - HTTP transport (streamable-http) on port 9000
供 OpenClaw 等 MCP 客户端调用

运行方式: python3 mcp_server.py
端口: 9000
"""
import json
import logging
import uuid
from mcp.server.fastmcp import FastMCP
from storage.postgres import PostgresStorage
from models.task import TaskCreate
from processors.video_downloader import video_downloader
from processors.transcriber import transcriber
from processors.content_processor import content_processor
from bot.content_analysis import ContentAnalyzer
from bot.conversation_engine import ConversationEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pkos-mcp")

mcp = FastMCP("pkos")
analyzer = ContentAnalyzer()
engine = ConversationEngine()


def _detect_platform(url: str) -> str:
    if "douyin.com" in url or "iesdouyin.com" in url:
        return "douyin"
    elif "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    return "unknown"


@mcp.tool()
async def process_video(url: str) -> str:
    """处理视频：下载→转录→AI优化→自动生成摘要。
    支持抖音和B站链接。处理完成后返回摘要和 task_id（后续用于对话和分析）。
    注意：处理需要数分钟，请耐心等待。"""
    logger.info(f"process_video: {url}")
    try:
        audio_path, title = await video_downloader.download(url)
        logger.info(f"Downloaded: {title}")

        raw_content = transcriber.transcribe(audio_path)
        logger.info(f"Transcribed: {len(raw_content)} chars")

        processed_content = await content_processor.process(raw_content, title)
        logger.info(f"Processed: {len(processed_content)} chars")

        storage = PostgresStorage()
        await storage.connect()
        platform = _detect_platform(url)
        task_uuid = str(uuid.uuid4())[:8]
        task_create = TaskCreate(
            task_id=task_uuid,
            video_url=url,
            platform=platform
        )
        task = await storage.create_task(task_create)
        await storage.update_task(
            task.task_id,
            status="completed",
            title=title,
            content=processed_content,
            raw_transcript=raw_content
        )
        await storage.disconnect()

        summary = await analyzer.generate_summary(processed_content)

        return json.dumps({
            "status": "success",
            "task_id": task.id,
            "title": title,
            "platform": platform,
            "content_length": len(processed_content),
            "summary": summary
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"process_video failed: {e}", exc_info=True)
        return json.dumps({"status": "failed", "error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def list_tasks(limit: int = 10) -> str:
    """列出最近已处理完成的视频任务，返回 task_id、标题、平台和完成时间。
    使用返回的 task_id 调用 chat_content 或 analyze_content 进行进一步操作。"""
    logger.info(f"list_tasks: limit={limit}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=limit)
        await storage.disconnect()

        if not tasks:
            return "暂无已处理的视频记录。"

        result = []
        for t in tasks:
            completed_str = t.completed_at.strftime('%Y-%m-%d %H:%M') if t.completed_at else "未知"
            result.append({
                "task_id": t.id,
                "title": t.title,
                "platform": t.platform,
                "completed_at": completed_str
            })

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"list_tasks failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_task(task_id: int) -> str:
    """获取指定任务的详情和内容预览（前500字）。
    task_id 来自 list_tasks 的返回结果。"""
    logger.info(f"get_task: task_id={task_id}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            return f"未找到 task_id={task_id} 的任务。"

        content_preview = None
        if task.content:
            content_preview = task.content[:500] + "..." if len(task.content) > 500 else task.content

        return json.dumps({
            "task_id": task.id,
            "title": task.title,
            "platform": task.platform,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "content_length": len(task.content) if task.content else 0,
            "content_preview": content_preview
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_task failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def chat_content(task_id: int, question: str, mode: str = "normal") -> str:
    """基于视频内容回答问题。
    task_id: 来自 list_tasks 的任务ID。
    question: 你的问题。
    mode: 'normal'（直接回答）或 'learning'（苏格拉底式，通过提问引导思考，不直接给答案）。"""
    logger.info(f"chat_content: task_id={task_id}, mode={mode}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            return f"未找到 task_id={task_id} 的任务。"
        if not task.content:
            return f"任务 {task_id} 没有可用内容，可能还在处理中。"

        response = await engine.generate_response(
            question=question,
            article_content=task.content,
            mode=mode,
            history=[]
        )
        return response

    except Exception as e:
        logger.error(f"chat_content failed: {e}", exc_info=True)
        return f"回答失败: {str(e)}"


@mcp.tool()
async def analyze_content(task_id: int, type: str = "summary") -> str:
    """对视频内容生成结构化分析。
    task_id: 来自 list_tasks 的任务ID。
    type 可选值:
    - 'summary': 300-500字精炼总结
    - 'outline': 层级大纲
    - 'qa': 5-8个核心问答对
    - 'extensions': 扩展思考方向（仅提供思考方向，不给出答案）"""
    logger.info(f"analyze_content: task_id={task_id}, type={type}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            return f"未找到 task_id={task_id} 的任务。"
        if not task.content:
            return f"任务 {task_id} 没有可用内容。"

        if type == "summary":
            result = await analyzer.generate_summary(task.content)
        elif type == "outline":
            result = await analyzer.generate_outline(task.content)
        elif type == "qa":
            result = await analyzer.generate_qa(task.content)
        elif type == "extensions":
            result = await analyzer.generate_extensions(task.content)
        else:
            return f"未知的分析类型: '{type}'。可选: summary, outline, qa, extensions"

        return result

    except Exception as e:
        logger.error(f"analyze_content failed: {e}", exc_info=True)
        return f"分析失败: {str(e)}"


if __name__ == "__main__":
    logger.info("Starting PKOS MCP server on port 9000 (streamable-http)...")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9000)
