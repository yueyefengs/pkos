#!/usr/bin/env python3
"""
PKOS MCP Server v2 - 精简版
融合卡帕西工作流，3个核心工具

运行方式: python3 mcp_server_v2.py [stdio|http]
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from storage.postgres import storage as db
from processors.unified_processor import unified_processor
from bot.conversation_engine import ConversationEngine
from config.settings import settings
from config.logger import logger

# MCP 服务
mcp = FastMCP("pkos", host="0.0.0.0", port=9000)
engine = ConversationEngine()


# ============================================================================
# 后台任务管理
# ============================================================================

background_tasks = {}


def _cleanup_background_task(task_id: int) -> None:
    """后台 digest 结束后释放任务引用，避免常驻内存。"""
    background_tasks.pop(task_id, None)


def _parse_wiki_paths(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _extract_query_terms(question: str) -> list[str]:
    """提取适合做检索的关键词，兼顾中文和英文。"""
    lowered = question.lower()
    english_terms = re.findall(r"[a-z0-9_]{2,}", lowered)
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", question)

    terms = []
    seen = set()
    for term in english_terms + chinese_terms:
        normalized = term.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            terms.append(normalized)
    return terms


def _find_relevant_notes(question: str, wiki_dir: Path, limit: int = 5) -> list[dict]:
    """从 wiki 中做一个简单但可用的相关性排序。"""
    question_lower = question.lower()
    query_terms = _extract_query_terms(question)
    relevant_notes = []

    for md_file in wiki_dir.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        text_lower = text.lower()
        title = md_file.stem
        title_lower = title.lower()
        score = 0

        if question_lower and question_lower in text_lower:
            score += 10
        if question_lower and question_lower in title_lower:
            score += 15

        for term in query_terms:
            if term in title_lower:
                score += 5
            occurrences = text_lower.count(term)
            if occurrences:
                score += min(occurrences, 5)

        if score == 0:
            continue

        relevant_notes.append({
            "title": title,
            "path": str(md_file),
            "score": score,
            "content": text[:2000],
        })

    relevant_notes.sort(key=lambda note: (-note["score"], note["title"]))
    return relevant_notes[:limit]


async def run_async_digest(task_id: int, task_uuid: str, raw_file: str):
    """
    后台执行消化流程
    
    流程：
    1. 消化到 wiki
    2. 更新数据库状态
    3. 更新索引
    4. 健康检查
    """
    try:
        logger.info(f"[Background] Starting digest for task {task_id}")
        
        # 消化到 wiki
        wiki_paths = await unified_processor.digest_to_wiki(raw_file)
        
        # 更新索引
        unified_processor.update_index()
        
        # 更新数据库
        try:
            await db.connect()
            await db.update_task(
                task_uuid,
                status="completed",
                wiki_paths=json.dumps(wiki_paths, ensure_ascii=False),
                completed_at=datetime.now()
            )
        finally:
            await db.disconnect()
        
        logger.info(f"[Background] Digest completed: {len(wiki_paths)} wiki notes")
        
    except Exception as e:
        logger.error(f"[Background] Digest failed: {e}", exc_info=True)
        try:
            await db.connect()
            await db.update_task(
                task_uuid,
                status="failed",
                error_message=str(e)
            )
        finally:
            await db.disconnect()


# ============================================================================
# 工具 1: ingest - 统一摄入
# ============================================================================

@mcp.tool()
async def ingest(
    content: str,
    source_type: str = "",
    title: str = "",
    digest: bool = True
) -> str:
    """
    统一知识摄入入口。自动识别内容类型并执行完整工作流。
    
    支持的内容：
    - 视频链接：抖音、B站、YouTube
    - 文章链接：任意网页
    - 音频链接：mp3、m4a 等
    - 文本内容：直接传入文本
    
    工作流（自动执行）：
    1. 识别内容类型
    2. 获取/处理内容（下载、转录、提取）
    3. 摄取到 /raw 目录
    4. [异步] 消化到 /wiki 目录
    5. [异步] 更新索引和健康检查
    
    参数：
    - content: URL 或文本内容（必填）
    - source_type: 强制指定类型，可选 "视频"/"文章"/"音频"/"文本"（默认自动识别）
    - title: 标题（可选）
    - digest: 是否自动消化到 wiki（默认 True）
    
    返回：处理结果摘要
    """
    logger.info(f"ingest: content_type auto-detect, title={title}")
    
    try:
        # 1. 检测内容类型
        detected_type = source_type or unified_processor.detect_content_type(content)
        
        # 类型映射
        type_map = {
            'video': '视频',
            'article': '文章',
            'audio': '音频',
            'text': '文本'
        }
        source_type_cn = type_map.get(detected_type, detected_type)
        
        # 2. 获取内容
        processed_content = ""
        raw_content = ""
        platform = ""
        
        if detected_type == 'video':
            title, raw_content, processed_content = await unified_processor.fetch_video(content)
            platform = "douyin" if "douyin" in content else "bilibili" if "bilibili" in content else "youtube"
            
        elif detected_type == 'article':
            title, processed_content = await unified_processor.fetch_article(content)
            raw_content = processed_content
            platform = "web"
            
        elif detected_type == 'audio':
            title, raw_content, processed_content = await unified_processor.fetch_audio(content)
            platform = "audio"
            
        else:  # text
            processed_content = content
            raw_content = content
            platform = "text"
            if not title:
                title = f"笔记-{datetime.now().strftime('%H%M%S')}"
        
        # 3. 摄取到 raw
        raw_file = unified_processor.ingest_to_raw(
            content=processed_content,
            source_type=source_type_cn,
            title=title,
            source_url=content if content.startswith('http') else ""
        )
        
        # 4. 创建数据库任务
        task_id = None
        task_uuid = None
        try:
            await db.connect()
            from models.task import TaskCreate
            import uuid
            task_create = TaskCreate(
                task_id=uuid.uuid4().hex[:8],
                video_url=content if detected_type in ['video', 'audio'] else "",
                platform=platform
            )
            task = await db.create_task(task_create)
            task_id = task.id
            task_uuid = task.task_id
            await db.update_task(
                task_uuid,
                status="digesting" if digest else "completed",
                title=title,
                content=processed_content,
                raw_transcript=raw_content,
                wiki_paths="[]" if not digest else None,
                completed_at=datetime.now() if not digest else None
            )
        finally:
            await db.disconnect()
        
        # 5. 异步消化（后台执行）
        if digest:
            task = asyncio.create_task(
                run_async_digest(task_id, task_uuid, raw_file)
            )
            task.add_done_callback(lambda _: _cleanup_background_task(task_id))
            background_tasks[task_id] = task
        
        # 6. 返回结果
        result = {
            "status": "success",
            "task_id": task_id,
            "title": title,
            "type": source_type_cn,
            "platform": platform,
            "content_length": len(processed_content),
            "raw_file": raw_file,
            "digest_status": "running" if digest else "skipped"
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"ingest failed: {e}", exc_info=True)
        return json.dumps({"status": "failed", "error": str(e)}, ensure_ascii=False)


# ============================================================================
# 工具 2: get_task - 查询任务状态
# ============================================================================

@mcp.tool()
async def get_task(task_id: int) -> str:
    """
    获取任务详情，包括 digest 状态和 wiki 产物路径。
    """
    logger.info(f"get_task: task_id={task_id}")

    try:
        try:
            await db.connect()
            task = await db.get_task_by_id(task_id)
        finally:
            await db.disconnect()

        if not task:
            return json.dumps({"status": "not_found", "task_id": task_id}, ensure_ascii=False)

        result = {
            "task_id": task.id,
            "task_uuid": task.task_id,
            "title": task.title or "无标题",
            "platform": task.platform or "",
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "content_length": len(task.content) if task.content else 0,
            "raw_transcript_length": len(task.raw_transcript) if task.raw_transcript else 0,
            "wiki_paths": _parse_wiki_paths(task.wiki_paths),
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_task failed: {e}", exc_info=True)
        return json.dumps({"status": "failed", "error": str(e)}, ensure_ascii=False)


# ============================================================================
# 工具 3: query - 知识查询
# ============================================================================

@mcp.tool()
async def query(
    question: str,
    task_id: int = 0,
    mode: str = "normal",
    history: str = ""
) -> str:
    """
    知识库查询。综合 wiki 和历史任务回答问题。问答结束后自动将新知识异步回写到 wiki。

    参数：
    - question: 问题（必填）
    - task_id: 限定在某个任务范围内（可选，0 表示搜索全库）
    - mode: 回答模式
      - "normal": 直接回答
      - "learning": 苏格拉底式，通过提问引导思考，不直接给答案
    - history: 对话历史（JSON 字符串，格式 [{"role":"user","content":"..."},...]，可选）

    返回：回答内容
    """
    logger.info(f"query: task_id={task_id}, mode={mode}")

    try:
        content = ""
        relevant_paths: list[str] = []

        # 解析对话历史
        history_list: list[dict] = []
        if history:
            try:
                history_list = json.loads(history)
            except Exception:
                logger.warning("query: failed to parse history JSON, ignoring")

        # 指定任务范围
        if task_id > 0:
            try:
                await db.connect()
                task = await db.get_task_by_id(task_id)
            finally:
                await db.disconnect()

            if not task:
                return f"未找到 task_id={task_id} 的任务。"

            if not task.content:
                return f"任务 {task_id} 没有可用内容。"

            content = task.content
            source = f"任务 {task_id}：{task.title}"

        # 全库搜索
        else:
            vault_path = Path(settings.obsidian_vault_path) if settings.obsidian_vault_path else None
            if not vault_path:
                return "知识库未配置 OBSIDIAN_VAULT_PATH"

            wiki_dir = vault_path / "wiki"
            if not wiki_dir.exists():
                return "知识库为空，请先使用 ingest 摄入内容"

            relevant_notes = _find_relevant_notes(question, wiki_dir)
            if not relevant_notes:
                return f"知识库中没有找到与「{question}」相关的内容"

            relevant_paths = [note["path"] for note in relevant_notes]
            content = "\n\n---\n\n".join(
                f"### {note['title']}\n路径：{note['path']}\n\n{note['content']}"
                for note in relevant_notes
            )
            source = f"知识库（{len(relevant_notes)} 条相关笔记）"

        # 调用对话引擎
        response = await engine.generate_response(
            question=question,
            article_content=content,
            mode=mode,
            history=history_list
        )

        # 异步回写新知识（仅全库搜索模式，task_id 模式不触发回写）
        if relevant_paths:
            wb_task = asyncio.create_task(
                unified_processor.writeback_from_qa(question, response, relevant_paths)
            )
            wb_task.add_done_callback(
                lambda t: logger.error(f"[Query] writeback failed: {t.exception()}")
                if not t.cancelled() and t.exception()
                else None
            )

        return f"**来源**：{source}\n\n{response}"

    except Exception as e:
        logger.error(f"query failed: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


# ============================================================================
# 工具 4: list - 任务列表
# ============================================================================

@mcp.tool()
async def list(limit: int = 10) -> str:
    """
    列出最近处理的内容。
    
    参数：
    - limit: 返回数量（默认 10）
    
    返回：任务列表
    """
    logger.info(f"list: limit={limit}")
    
    try:
        try:
            await db.connect()
            tasks = await db.get_recent_tasks(limit=limit)
        finally:
            await db.disconnect()
        
        if not tasks:
            return "暂无处理记录。"
        
        result = []
        for t in tasks:
            completed_str = t.completed_at.strftime('%Y-%m-%d %H:%M') if t.completed_at else "处理中"
            result.append({
                "task_id": t.id,
                "title": t.title or "无标题",
                "platform": t.platform or "",
                "completed_at": completed_str
            })
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"list failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================================
# 启动
# ============================================================================

if __name__ == "__main__":
    import sys
    transport = "stdio" if len(sys.argv) == 1 else sys.argv[1]
    
    if transport == "stdio":
        logger.info("Starting PKOS MCP v2 (stdio)...")
        mcp.run(transport="stdio")
    else:
        logger.info("Starting PKOS MCP v2 on port 9000 (streamable-http)...")
        mcp.run(transport="streamable-http")
