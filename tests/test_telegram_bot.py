"""
Telegram Bot基础功能测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from bot.session_manager import SessionManager
from storage.postgres import storage
from models.task import TaskCreate


@pytest.mark.asyncio
async def test_session_manager():
    """测试会话管理器基本功能"""
    session = SessionManager()
    await session.connect()

    user_id = "test_user_123"

    # 测试工作区操作
    await session.add_to_workspace(user_id, 1)
    workspace = await session.get_workspace(user_id)
    assert 1 in workspace

    # 测试模式切换
    await session.set_mode(user_id, "learning")
    mode = await session.get_mode(user_id)
    assert mode == "learning"

    # 测试对话历史
    await session.add_message(user_id, "user", "测试消息")
    history = await session.get_history(user_id, limit=1)
    assert len(history) == 1
    assert history[0]["content"] == "测试消息"

    # 清理
    await session.clear_workspace(user_id)
    await session.clear_history(user_id)
    await session.disconnect()

    print("✅ Session manager test passed")


@pytest.mark.asyncio
async def test_storage():
    """测试数据库存储基本功能"""
    await storage.connect()

    # 创建测试任务
    task_create = TaskCreate(
        task_id="test_task_123",
        video_url="https://example.com/video",
        platform="bilibili"
    )
    task = await storage.create_task(task_create)
    assert task.id is not None
    assert task.platform == "bilibili"

    # 测试学习进度
    progress = await storage.get_or_create_progress("test_user", task.id)
    assert progress.id is not None
    assert progress.user_id == "test_user"

    # 更新进度
    updated = await storage.update_progress(progress.id, questions_asked=5)
    assert updated.questions_asked == 5

    await storage.disconnect()

    print("✅ Storage test passed")


def test_imports():
    """测试所有模块导入正常"""
    try:
        from bot.telegram_client import get_telegram_client
        from bot.session_manager import get_session_manager
        from bot.command_handlers import start_command, help_command
        from bot.message_handler import handle_message
        from bot.conversation_engine import ConversationEngine
        from bot.content_analysis import ContentAnalyzer
        from bot.progress_tracker import progress_command
        from bot.telegram_main import main

        print("✅ All imports successful")
    except Exception as e:
        pytest.fail(f"Import failed: {e}")


if __name__ == "__main__":
    print("运行Telegram Bot测试...")
    print("-" * 50)

    # 测试导入
    test_imports()

    # 注意: 异步测试需要运行环境支持
    # 可以使用: pytest tests/test_telegram_bot.py
    print("\n运行完整测试请使用: pytest tests/test_telegram_bot.py")
