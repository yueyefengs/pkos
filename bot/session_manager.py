"""
Redis会话管理器
管理用户工作区(激活的文章)、对话历史、学习模式等
"""
import json
import aioredis
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from config.settings import settings
from config.logger import logger


class SessionManager:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """连接到Redis"""
        self.redis = await aioredis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Redis session manager connected")

    async def disconnect(self):
        """关闭Redis连接"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis session manager disconnected")

    # ===== 工作区管理 =====

    def _workspace_key(self, user_id: str) -> str:
        """工作区键名"""
        return f"workspace:{user_id}"

    async def get_workspace(self, user_id: str) -> List[int]:
        """
        获取用户工作区中的任务ID列表

        Returns:
            List[int]: 任务ID列表(task表的id,不是task_id)
        """
        key = self._workspace_key(user_id)
        task_ids = await self.redis.lrange(key, 0, -1)
        return [int(tid) for tid in task_ids] if task_ids else []

    async def add_to_workspace(self, user_id: str, task_id: int) -> None:
        """
        添加任务到工作区

        Args:
            user_id: 用户ID
            task_id: 任务ID(task表的id)
        """
        key = self._workspace_key(user_id)
        # 检查是否已存在
        exists = await self.redis.lpos(key, str(task_id))
        if exists is None:
            await self.redis.rpush(key, str(task_id))
            await self.redis.expire(key, 86400 * 7)  # 7天过期
            logger.debug(f"Added task {task_id} to workspace of user {user_id}")

    async def remove_from_workspace(self, user_id: str, task_id: int) -> bool:
        """
        从工作区移除任务

        Returns:
            bool: 是否成功移除
        """
        key = self._workspace_key(user_id)
        removed = await self.redis.lrem(key, 0, str(task_id))
        return removed > 0

    async def clear_workspace(self, user_id: str) -> None:
        """清空工作区"""
        key = self._workspace_key(user_id)
        await self.redis.delete(key)
        logger.debug(f"Cleared workspace of user {user_id}")

    # ===== 模式管理 =====

    def _mode_key(self, user_id: str) -> str:
        """模式键名"""
        return f"mode:{user_id}"

    async def get_mode(self, user_id: str) -> str:
        """
        获取用户的对话模式

        Returns:
            str: "normal" 或 "learning"
        """
        key = self._mode_key(user_id)
        mode = await self.redis.get(key)
        return mode if mode else "normal"

    async def set_mode(self, user_id: str, mode: str) -> None:
        """
        设置用户的对话模式

        Args:
            mode: "normal" 或 "learning"
        """
        if mode not in ["normal", "learning"]:
            raise ValueError(f"Invalid mode: {mode}")

        key = self._mode_key(user_id)
        await self.redis.set(key, mode)
        await self.redis.expire(key, 86400 * 7)  # 7天过期
        logger.debug(f"Set mode {mode} for user {user_id}")

    # ===== 对话历史管理 =====

    def _history_key(self, user_id: str) -> str:
        """对话历史键名"""
        return f"history:{user_id}"

    async def add_message(self, user_id: str, role: str, content: str) -> None:
        """
        添加对话消息到历史

        Args:
            user_id: 用户ID
            role: "user" 或 "assistant"
            content: 消息内容
        """
        key = self._history_key(user_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        await self.redis.rpush(key, json.dumps(message, ensure_ascii=False))
        await self.redis.expire(key, 86400 * 7)  # 7天过期

        # 限制历史长度为最近50条
        await self.redis.ltrim(key, -50, -1)

    async def get_history(self, user_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        获取对话历史

        Args:
            user_id: 用户ID
            limit: 获取最近N条消息

        Returns:
            List[Dict]: [{"role": "user", "content": "...", "timestamp": "..."}]
        """
        key = self._history_key(user_id)
        messages = await self.redis.lrange(key, -limit, -1)
        return [json.loads(msg) for msg in messages] if messages else []

    async def clear_history(self, user_id: str) -> None:
        """清空对话历史"""
        key = self._history_key(user_id)
        await self.redis.delete(key)
        logger.debug(f"Cleared history of user {user_id}")

    # ===== 学习时间追踪 =====

    def _study_time_key(self, user_id: str, task_id: int) -> str:
        """学习时间键名"""
        return f"study_time:{user_id}:{task_id}"

    async def start_study_session(self, user_id: str, task_id: int) -> None:
        """开始学习会话,记录开始时间"""
        key = self._study_time_key(user_id, task_id)
        await self.redis.set(key, str(int(datetime.now().timestamp())))
        await self.redis.expire(key, 86400)  # 1天过期

    async def end_study_session(self, user_id: str, task_id: int) -> int:
        """
        结束学习会话,计算学习时长

        Returns:
            int: 学习时长(秒)
        """
        key = self._study_time_key(user_id, task_id)
        start_time_str = await self.redis.get(key)
        if not start_time_str:
            return 0

        start_time = int(start_time_str)
        end_time = int(datetime.now().timestamp())
        duration = end_time - start_time

        await self.redis.delete(key)
        return duration

    # ===== 辅助方法 =====

    async def get_workspace_info(self, user_id: str) -> Dict:
        """
        获取用户的完整工作区信息

        Returns:
            Dict: {
                "task_ids": List[int],
                "mode": str,
                "message_count": int
            }
        """
        task_ids = await self.get_workspace(user_id)
        mode = await self.get_mode(user_id)
        history = await self.get_history(user_id, limit=1)
        message_count = len(history)

        return {
            "task_ids": task_ids,
            "mode": mode,
            "message_count": message_count
        }


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
