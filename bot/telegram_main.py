"""
Telegram Bot主程序
整合所有功能模块,启动bot服务
"""
import asyncio
import os
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)
from telegram.request import HTTPXRequest
from bot.telegram_client import get_telegram_client
from bot.session_manager import get_session_manager
from bot.command_handlers import (
    start_command,
    help_command,
    history_command,
    chat_command,
    learn_command,
    context_command,
    clear_command,
    add_command,
    mode_command
)
from bot.content_analysis import (
    outline_command,
    summary_command,
    qa_command,
    extend_command
)
from bot.progress_tracker import (
    progress_command,
    workspace_command,
    stats_command,
    checkpoint_command
)
from bot.message_handler import handle_message
from storage.postgres import storage
from config.settings import settings
from config.logger import logger


async def post_init(application: Application):
    """
    Bot启动后的初始化
    连接数据库和Redis
    """
    logger.info("Initializing Telegram bot...")

    # 初始化Telegram客户端
    client = get_telegram_client()
    await client.initialize()

    # 连接数据库
    await storage.connect()
    logger.info("Database connected")

    # 连接Redis
    session_manager = get_session_manager()
    await session_manager.connect()
    logger.info("Redis session manager connected")

    logger.info("Telegram bot initialization complete")


async def post_shutdown(application: Application):
    """
    Bot关闭时的清理工作
    断开数据库和Redis连接
    """
    logger.info("Shutting down Telegram bot...")

    # 断开数据库
    await storage.disconnect()
    logger.info("Database disconnected")

    # 断开Redis
    session_manager = get_session_manager()
    await session_manager.disconnect()
    logger.info("Redis disconnected")

    logger.info("Telegram bot shutdown complete")


def main():
    """主函数 - 创建并运行bot"""
    logger.info("Starting Telegram bot...")

    # 配置代理（从环境变量读取）
    proxy_url = os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')

    # 创建Application
    builder = Application.builder().token(settings.telegram_bot_token)

    if proxy_url:
        logger.info(f"Configuring Application with proxy: {proxy_url}")
        # 创建带代理的请求对象
        # 注意：参数名是 proxy，不是 proxy_url
        request = HTTPXRequest(
            proxy=proxy_url,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0
        )
        # get_updates 用于轮询，也需要配置代理
        get_updates_request = HTTPXRequest(
            proxy=proxy_url,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0
        )
        builder = builder.request(request).get_updates_request(get_updates_request)
    else:
        logger.info("No proxy configured for Application")

    application = (
        builder
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ===== 注册命令处理器 =====

    # 基础命令
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # 工作区管理命令
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("learn", learn_command))
    application.add_handler(CommandHandler("context", context_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("mode", mode_command))

    # 内容分析命令
    application.add_handler(CommandHandler("outline", outline_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("qa", qa_command))
    application.add_handler(CommandHandler("extend", extend_command))

    # 进度追踪命令
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("workspace", workspace_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("checkpoint", checkpoint_command))

    # 普通文本消息处理器
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("All handlers registered")

    # 启动Long Polling
    logger.info(f"Starting bot polling... (Bot: {settings.telegram_bot_username})")
    application.run_polling(
        allowed_updates=["message"],
        drop_pending_updates=True
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
