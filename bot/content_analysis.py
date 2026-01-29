"""
内容分析功能
提供大纲、总结、问答、扩展阅读生成
"""
from telegram import Update
from telegram.ext import ContextTypes
from bot.session_manager import get_session_manager
from bot.telegram_client import get_telegram_client
from storage.postgres import storage
from processors.llm_client import llm_client
from config.logger import logger


class ContentAnalyzer:
    """内容分析器"""

    @staticmethod
    async def generate_outline(content: str) -> str:
        """生成内容大纲"""
        prompt = f"""请为以下内容生成一个清晰的大纲(outline)。

要求:
1. 使用层级结构(一级、二级、三级标题)
2. 提取核心观点和主要论述
3. 保持逻辑清晰,层次分明
4. 使用简洁的语言

内容:
{content[:6000]}

请生成大纲:"""

        response = await llm_client.generate_chat_response(prompt)
        return response

    @staticmethod
    async def generate_summary(content: str) -> str:
        """生成内容总结"""
        prompt = f"""请为以下内容生成一个精炼的总结。

要求:
1. 提取核心要点(3-5个)
2. 保留关键信息和结论
3. 篇幅控制在300-500字
4. 使用清晰的分点格式

内容:
{content[:6000]}

请生成总结:"""

        response = await llm_client.generate_chat_response(prompt)
        return response

    @staticmethod
    async def generate_qa(content: str) -> str:
        """生成常见问答"""
        prompt = f"""基于以下内容,生成5-8个读者可能关心的问题及答案。

要求:
1. 问题覆盖核心知识点
2. 答案简洁明了(每个50-100字)
3. 使用Q&A格式
4. 问题具有代表性和实用性

内容:
{content[:6000]}

请生成Q&A:"""

        response = await llm_client.generate_chat_response(prompt)
        return response

    @staticmethod
    async def generate_extensions(content: str) -> str:
        """生成扩展阅读建议"""
        prompt = f"""基于以下内容,提出3-5个扩展思考方向。

重要:
1. 仅提出思考方向,不提供答案
2. 引导读者主动探索和思考
3. 覆盖不同维度(理论深化、实践应用、对比分析等)
4. 保持开放性,鼓励批判性思维

内容:
{content[:6000]}

请提出扩展思考方向:"""

        response = await llm_client.generate_chat_response(prompt)
        return response


# ===== 命令处理函数 =====

async def outline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /outline 命令 - 生成内容大纲"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    client = get_telegram_client()
    session = get_session_manager()

    try:
        # 获取工作区
        await session.connect()
        workspace_ids = await session.get_workspace(user_id)
        await session.disconnect()

        if not workspace_ids:
            await client.send_message(
                chat_id,
                "📭 工作区为空\n\n使用 `/chat [任务ID]` 激活文章"
            )
            return

        # 获取文章内容
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=100)
        await storage.disconnect()

        active_tasks = [t for t in tasks if t.id in workspace_ids]
        if not active_tasks or not active_tasks[0].content:
            await client.send_message(
                chat_id,
                "❌ 找不到文章内容"
            )
            return

        article = active_tasks[0]

        # 生成大纲
        await client.send_message(chat_id, "📝 正在生成大纲...")
        outline = await ContentAnalyzer.generate_outline(article.content)

        # 发送结果
        result = f"📋 **内容大纲**\n\n{article.title}\n\n---\n\n{outline}"
        await client.send_long_message(chat_id, result)

        logger.info(f"Generated outline for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to generate outline: {e}")
        await client.send_message(
            chat_id,
            f"❌ 生成大纲失败: {str(e)}"
        )


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /summary 命令 - 生成内容总结"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    client = get_telegram_client()
    session = get_session_manager()

    try:
        # 获取工作区
        await session.connect()
        workspace_ids = await session.get_workspace(user_id)
        await session.disconnect()

        if not workspace_ids:
            await client.send_message(
                chat_id,
                "📭 工作区为空\n\n使用 `/chat [任务ID]` 激活文章"
            )
            return

        # 获取文章内容
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=100)
        await storage.disconnect()

        active_tasks = [t for t in tasks if t.id in workspace_ids]
        if not active_tasks or not active_tasks[0].content:
            await client.send_message(
                chat_id,
                "❌ 找不到文章内容"
            )
            return

        article = active_tasks[0]

        # 生成总结
        await client.send_message(chat_id, "📝 正在生成总结...")
        summary = await ContentAnalyzer.generate_summary(article.content)

        # 发送结果
        result = f"📄 **内容总结**\n\n{article.title}\n\n---\n\n{summary}"
        await client.send_long_message(chat_id, result)

        logger.info(f"Generated summary for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        await client.send_message(
            chat_id,
            f"❌ 生成总结失败: {str(e)}"
        )


async def qa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /qa 命令 - 生成常见问答"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    client = get_telegram_client()
    session = get_session_manager()

    try:
        # 获取工作区
        await session.connect()
        workspace_ids = await session.get_workspace(user_id)
        await session.disconnect()

        if not workspace_ids:
            await client.send_message(
                chat_id,
                "📭 工作区为空\n\n使用 `/chat [任务ID]` 激活文章"
            )
            return

        # 获取文章内容
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=100)
        await storage.disconnect()

        active_tasks = [t for t in tasks if t.id in workspace_ids]
        if not active_tasks or not active_tasks[0].content:
            await client.send_message(
                chat_id,
                "❌ 找不到文章内容"
            )
            return

        article = active_tasks[0]

        # 生成问答
        await client.send_message(chat_id, "📝 正在生成常见问答...")
        qa = await ContentAnalyzer.generate_qa(article.content)

        # 发送结果
        result = f"❓ **常见问答**\n\n{article.title}\n\n---\n\n{qa}"
        await client.send_long_message(chat_id, result)

        logger.info(f"Generated Q&A for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to generate Q&A: {e}")
        await client.send_message(
            chat_id,
            f"❌ 生成问答失败: {str(e)}"
        )


async def extend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /extend 命令 - 生成扩展阅读建议"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    client = get_telegram_client()
    session = get_session_manager()

    try:
        # 获取工作区
        await session.connect()
        workspace_ids = await session.get_workspace(user_id)
        await session.disconnect()

        if not workspace_ids:
            await client.send_message(
                chat_id,
                "📭 工作区为空\n\n使用 `/chat [任务ID]` 激活文章"
            )
            return

        # 获取文章内容
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=100)
        await storage.disconnect()

        active_tasks = [t for t in tasks if t.id in workspace_ids]
        if not active_tasks or not active_tasks[0].content:
            await client.send_message(
                chat_id,
                "❌ 找不到文章内容"
            )
            return

        article = active_tasks[0]

        # 生成扩展建议
        await client.send_message(chat_id, "📝 正在生成扩展阅读建议...")
        extensions = await ContentAnalyzer.generate_extensions(article.content)

        # 发送结果
        result = f"🔍 **扩展思考**\n\n{article.title}\n\n---\n\n{extensions}"
        await client.send_long_message(chat_id, result)

        logger.info(f"Generated extensions for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to generate extensions: {e}")
        await client.send_message(
            chat_id,
            f"❌ 生成扩展建议失败: {str(e)}"
        )
