"""
学习进度追踪功能
提供进度查看、统计和检查点管理
"""
from telegram import Update
from telegram.ext import ContextTypes
from bot.session_manager import get_session_manager
from bot.telegram_client import get_telegram_client, escape_markdown_v2
from storage.postgres import storage
from models.task import LearningStatus
from config.logger import logger
from datetime import datetime


async def show_task_progress(user_id: str, chat_id: str, task_id: int):
    """显示单个任务的学习进度"""
    client = get_telegram_client()

    try:
        await storage.connect()

        # 获取任务信息
        tasks = await storage.get_recent_tasks(limit=100)
        task = next((t for t in tasks if t.id == task_id), None)

        if not task:
            await storage.disconnect()
            await client.send_message(chat_id, "❌ 找不到任务")
            return

        # 获取学习进度
        progress = await storage.get_or_create_progress(user_id, task_id)

        # 获取概念掌握情况
        concepts = await storage.get_concepts_by_progress(progress.id)

        await storage.disconnect()

        # 格式化进度信息
        status_emoji = {
            LearningStatus.NOT_STARTED: "⚪",
            LearningStatus.IN_PROGRESS: "🟡",
            LearningStatus.COMPLETED: "🟢",
            LearningStatus.REVIEWING: "🔵"
        }

        message = f"📊 **学习进度**\n\n"
        message += f"**文章:** {task.title}\n"
        message += f"**状态:** {status_emoji.get(progress.status, '⚪')} {progress.status.value}\n"
        message += f"**学习时长:** {progress.study_time // 60} 分钟\n"
        message += f"**提问次数:** {progress.questions_asked}\n\n"

        if concepts:
            message += f"**概念掌握:** ({len(concepts)}个)\n"
            for concept in concepts[:10]:  # 最多显示10个
                status_icon = {"unknown": "⚪", "familiar": "🟡", "understood": "🟢", "mastered": "⭐"}
                icon = status_icon.get(concept.status.value, "⚪")
                message += f"{icon} {concept.concept}\n"

            if len(concepts) > 10:
                message += f"\n...还有 {len(concepts) - 10} 个概念\n"
        else:
            message += "**概念掌握:** 暂无记录\n"

        if progress.last_position:
            message += f"\n**上次位置:** {progress.last_position}\n"

        await client.send_message(chat_id, message)

    except Exception as e:
        logger.error(f"Failed to show progress: {e}")
        await client.send_message(chat_id, f"❌ 获取进度失败: {str(e)}")


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /progress 命令 - 显示当前文章学习进度"""
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
                "📭 工作区为空\n\n使用 `/learn [任务ID]` 激活学习模式"
            )
            return

        # 显示第一篇文章的进度
        await show_task_progress(user_id, chat_id, workspace_ids[0])

    except Exception as e:
        logger.error(f"Failed to show progress: {e}")
        await client.send_message(
            chat_id,
            f"❌ 获取进度失败: {str(e)}"
        )


async def workspace_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /workspace 命令 - 显示工作区所有文章的进度"""
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
                "📭 工作区为空\n\n使用 `/learn [任务ID]` 激活学习模式"
            )
            return

        # 获取所有进度
        await storage.connect()
        progress_list = await storage.get_user_progress_list(user_id)
        await storage.disconnect()

        # 过滤工作区中的文章
        workspace_progress = [(p, t) for p, t in progress_list if t.id in workspace_ids]

        if not workspace_progress:
            await client.send_message(
                chat_id,
                "📭 工作区中没有学习记录"
            )
            return

        # 格式化进度信息
        message = f"📚 **工作区学习进度**\n\n"

        for progress, task in workspace_progress:
            status_emoji = {
                LearningStatus.NOT_STARTED: "⚪",
                LearningStatus.IN_PROGRESS: "🟡",
                LearningStatus.COMPLETED: "🟢",
                LearningStatus.REVIEWING: "🔵"
            }

            message += f"{status_emoji.get(progress.status, '⚪')} **{escape_markdown_v2(task.title)}**\n"
            message += f"   学习 {progress.study_time // 60} 分钟 | 提问 {progress.questions_asked} 次\n"
            message += f"   任务ID: `{task.id}`\n\n"

        message += "\n使用 `/progress` 查看详细进度"

        await client.send_message(chat_id, message)

    except Exception as e:
        logger.error(f"Failed to show workspace progress: {e}")
        await client.send_message(
            chat_id,
            f"❌ 获取工作区进度失败: {escape_markdown_v2(str(e))}"
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /stats 命令 - 显示学习统计"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    client = get_telegram_client()

    try:
        # 获取所有学习进度
        await storage.connect()
        progress_list = await storage.get_user_progress_list(user_id)
        await storage.disconnect()

        if not progress_list:
            await client.send_message(
                chat_id,
                "📊 暂无学习记录\n\n使用 `/learn [任务ID]` 开始学习"
            )
            return

        # 计算统计数据
        total_articles = len(progress_list)
        total_time = sum(p.study_time for p, _ in progress_list)
        total_questions = sum(p.questions_asked for p, _ in progress_list)

        completed_count = sum(1 for p, _ in progress_list if p.status == LearningStatus.COMPLETED)
        in_progress_count = sum(1 for p, _ in progress_list if p.status == LearningStatus.IN_PROGRESS)

        # 格式化统计信息
        message = f"📈 **学习统计**\n\n"
        message += f"**文章总数:** {total_articles}\n"
        message += f"• 已完成: {completed_count}\n"
        message += f"• 学习中: {in_progress_count}\n"
        message += f"• 未开始: {total_articles - completed_count - in_progress_count}\n\n"

        message += f"**总学习时长:** {total_time // 60} 分钟 ({total_time // 3600} 小时)\n"
        message += f"**总提问次数:** {total_questions}\n"

        if total_articles > 0:
            avg_time = total_time // total_articles
            avg_questions = total_questions // total_articles
            message += f"\n**平均每篇:**\n"
            message += f"• 学习时长: {avg_time // 60} 分钟\n"
            message += f"• 提问次数: {avg_questions}\n"

        # 最近学习的文章
        recent = progress_list[:3]
        if recent:
            message += f"\n**最近学习:**\n"
            for progress, task in recent:
                message += f"• {task.title}\n"
                message += f"  {progress.updated_at.strftime('%Y-%m-%d %H:%M')}\n"

        await client.send_message(chat_id, message)

    except Exception as e:
        logger.error(f"Failed to show stats: {e}")
        await client.send_message(
            chat_id,
            f"❌ 获取统计失败: {str(e)}"
        )


async def checkpoint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /checkpoint 命令 - 保存学习检查点"""
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
                "📭 工作区为空\n\n使用 `/learn [任务ID]` 激活学习模式"
            )
            return

        # 获取当前学习进度
        await storage.connect()
        progress = await storage.get_or_create_progress(user_id, workspace_ids[0])

        # 保存检查点
        checkpoint_content = f"学习检查点 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        position = f"问题 #{progress.questions_asked}"

        await storage.save_checkpoint(progress.id, checkpoint_content, position)
        await storage.disconnect()

        await client.send_message(
            chat_id,
            f"✅ 学习检查点已保存\n\n"
            f"位置: {position}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        logger.info(f"Saved checkpoint for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")
        await client.send_message(
            chat_id,
            f"❌ 保存检查点失败: {str(e)}"
        )
