"""
Telegram Bot命令处理器
处理所有用户命令: /start, /help, /history, /chat, /learn, /context, /clear, /add, /mode
"""
from telegram import Update
from telegram.ext import ContextTypes
from bot.session_manager import get_session_manager
from bot.telegram_client import get_telegram_client, escape_markdown_v2
from storage.postgres import storage
from config.logger import logger


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    client = get_telegram_client()

    welcome_message = f"""
👋 你好, {user.first_name}!

我是视频学习助手,可以帮你:
📹 下载并转录视频(抖音/B站)
📝 生成内容大纲和总结
💬 针对内容进行问答
🎓 提供学习模式指导

**快速开始:**
1️⃣ 直接发送视频链接,我会自动处理
2️⃣ 处理完成后使用 `/chat [任务ID]` 激活文章
3️⃣ 开始提问或使用 `/learn [任务ID]` 进入学习模式

输入 `/help` 查看完整命令列表
"""

    await client.send_message(str(update.effective_chat.id), welcome_message)
    logger.info(f"User {user.id} started bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    client = get_telegram_client()

    help_text = """
📚 **命令列表**

**工作区管理:**
• `/chat [任务ID]` - 激活文章并进入普通对话模式
• `/learn [任务ID]` - 激活文章并进入学习模式
• `/add [任务ID]` - 添加文章到工作区
• `/context` - 查看当前工作区内容
• `/clear` - 清空工作区

**模式切换:**
• `/mode normal` - 切换到普通对话模式
• `/mode learning` - 切换到学习模式

**内容分析:**
• `/outline` - 生成内容大纲
• `/summary` - 生成内容总结
• `/qa` - 生成常见问题解答
• `/extend` - 生成扩展阅读建议

**进度追踪:**
• `/progress` - 查看当前文章学习进度
• `/workspace` - 查看工作区所有进度
• `/stats` - 查看学习统计
• `/checkpoint` - 保存学习检查点

**其他:**
• `/history` - 查看最近处理的视频
• `/help` - 显示此帮助信息

**使用提示:**
• 直接发送视频链接即可开始处理
• 工作区可以同时包含多篇文章
• 学习模式会用苏格拉底式教学方法引导你思考
"""

    await client.send_message(str(update.effective_chat.id), help_text)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /history 命令 - 显示最近处理的视频"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()

    try:
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=10)
        await storage.disconnect()

        if not tasks:
            await client.send_message(
                str(update.effective_chat.id),
                "暂无处理记录"
            )
            return

        message = "📜 **最近处理的视频:**\n\n"
        for task in tasks:
            message += f"• **{escape_markdown_v2(task.title)}**\n"
            message += f"  ID: `{task.id}` | 平台: {task.platform}\n"
            message += f"  完成时间: {task.completed_at.strftime('%Y-%m-%d %H:%M')}\n\n"

        message += "\n使用 `/chat [ID]` 激活文章进行对话"

        await client.send_message(str(update.effective_chat.id), message)

    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"获取历史记录失败: {escape_markdown_v2(str(e))}"
        )


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /chat 命令 - 激活文章并进入普通对话模式"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()
    session = get_session_manager()

    # 检查参数
    if not context.args or len(context.args) == 0:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 请提供任务ID\n用法: `/chat [任务ID]`"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 任务ID必须是数字"
        )
        return

    try:
        # 验证任务是否存在
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            await client.send_message(
                str(update.effective_chat.id),
                f"❌ 找不到任务ID {task_id}"
            )
            return

        # 清空并设置新工作区
        await session.connect()
        await session.clear_workspace(user_id)
        await session.add_to_workspace(user_id, task_id)
        await session.set_mode(user_id, "normal")
        await session.clear_history(user_id)
        await session.disconnect()

        await client.send_message(
            str(update.effective_chat.id),
            f"✅ 已激活文章: **{escape_markdown_v2(task.title)}**\n"
            f"模式: 普通对话\n\n"
            f"现在你可以针对这篇文章提问了!"
        )

    except Exception as e:
        logger.error(f"Failed to activate chat: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"激活失败: {escape_markdown_v2(str(e))}"
        )


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /learn 命令 - 激活文章并进入学习模式"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()
    session = get_session_manager()

    # 检查参数
    if not context.args or len(context.args) == 0:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 请提供任务ID\n用法: `/learn [任务ID]`"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 任务ID必须是数字"
        )
        return

    try:
        # 验证任务是否存在
        await storage.connect()
        task = await storage.get_task_by_id(task_id)

        if not task:
            await storage.disconnect()
            await client.send_message(
                str(update.effective_chat.id),
                f"❌ 找不到任务ID {task_id}"
            )
            return

        # 创建学习进度记录
        progress = await storage.get_or_create_progress(user_id, task_id)
        await storage.disconnect()

        # 清空并设置新工作区
        await session.connect()
        await session.clear_workspace(user_id)
        await session.add_to_workspace(user_id, task_id)
        await session.set_mode(user_id, "learning")
        await session.clear_history(user_id)
        await session.start_study_session(user_id, task_id)
        await session.disconnect()

        await client.send_message(
            str(update.effective_chat.id),
            f"🎓 已激活学习模式: **{escape_markdown_v2(task.title)}**\n\n"
            f"学习模式特点:\n"
            f"• 苏格拉底式教学方法\n"
            f"• 引导你主动思考\n"
            f"• 不直接给出答案\n"
            f"• 通过提问帮助理解\n\n"
            f"随时可以使用 `/mode normal` 切换回普通模式"
        )

    except Exception as e:
        logger.error(f"Failed to activate learning mode: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"激活学习模式失败: {escape_markdown_v2(str(e))}"
        )


async def context_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /context 命令 - 查看当前工作区内容"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()
    session = get_session_manager()

    try:
        await session.connect()
        workspace_info = await session.get_workspace_info(user_id)
        await session.disconnect()

        task_ids = workspace_info["task_ids"]

        if not task_ids:
            await client.send_message(
                str(update.effective_chat.id),
                "📭 工作区为空\n\n使用 `/chat [任务ID]` 或 `/learn [任务ID]` 激活文章"
            )
            return

        # 获取任务详情
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=100)
        await storage.disconnect()

        workspace_tasks = [t for t in tasks if t.id in task_ids]

        message = f"📂 **当前工作区**\n"
        message += f"模式: {workspace_info['mode']}\n"
        message += f"对话轮数: {workspace_info['message_count']}\n\n"

        for task in workspace_tasks:
            message += f"• **{escape_markdown_v2(task.title)}**\n"
            message += f"  ID: `{task.id}` | 平台: {task.platform}\n\n"

        await client.send_message(str(update.effective_chat.id), message)

    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"获取工作区信息失败: {escape_markdown_v2(str(e))}"
        )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /clear 命令 - 清空工作区"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()
    session = get_session_manager()

    try:
        await session.connect()
        await session.clear_workspace(user_id)
        await session.clear_history(user_id)
        await session.disconnect()

        await client.send_message(
            str(update.effective_chat.id),
            "✅ 工作区和对话历史已清空"
        )

    except Exception as e:
        logger.error(f"Failed to clear workspace: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"清空失败: {str(e)}"
        )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /add 命令 - 添加文章到工作区"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()
    session = get_session_manager()

    # 检查参数
    if not context.args or len(context.args) == 0:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 请提供任务ID\n用法: `/add [任务ID]`"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 任务ID必须是数字"
        )
        return

    try:
        # 验证任务是否存在
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            await client.send_message(
                str(update.effective_chat.id),
                f"❌ 找不到任务ID {task_id}"
            )
            return

        # 添加到工作区
        await session.connect()
        await session.add_to_workspace(user_id, task_id)
        workspace_info = await session.get_workspace_info(user_id)
        await session.disconnect()

        await client.send_message(
            str(update.effective_chat.id),
            f"✅ 已添加: **{escape_markdown_v2(task.title)}**\n"
            f"工作区文章数: {len(workspace_info['task_ids'])}"
        )

    except Exception as e:
        logger.error(f"Failed to add to workspace: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"添加失败: {escape_markdown_v2(str(e))}"
        )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /mode 命令 - 切换对话模式"""
    user_id = str(update.effective_user.id)
    client = get_telegram_client()
    session = get_session_manager()

    # 检查参数
    if not context.args or len(context.args) == 0:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 请指定模式\n用法: `/mode [normal|learning]`"
        )
        return

    mode = context.args[0].lower()
    if mode not in ["normal", "learning"]:
        await client.send_message(
            str(update.effective_chat.id),
            "❌ 无效的模式\n可选: `normal` 或 `learning`"
        )
        return

    try:
        await session.connect()
        await session.set_mode(user_id, mode)
        await session.disconnect()

        mode_name = "普通对话" if mode == "normal" else "学习模式"
        await client.send_message(
            str(update.effective_chat.id),
            f"✅ 已切换到: **{escape_markdown_v2(mode_name)}**"
        )

    except Exception as e:
        logger.error(f"Failed to switch mode: {e}")
        await client.send_message(
            str(update.effective_chat.id),
            f"切换模式失败: {escape_markdown_v2(str(e))}"
        )
