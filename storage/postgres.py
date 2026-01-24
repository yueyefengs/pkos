import asyncpg
from typing import Optional, List
from datetime import datetime
from config.settings import settings
from models.task import Task, TaskCreate, TaskStatus

class PostgresStorage:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """连接到PostgreSQL数据库"""
        self.pool = await asyncpg.create_pool(settings.database_url)
        await self._init_db()

    async def disconnect(self):
        """关闭数据库连接"""
        if self.pool:
            await self.pool.close()

    async def _init_db(self):
        """初始化数据库表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(36) UNIQUE NOT NULL,
            video_url TEXT NOT NULL,
            title VARCHAR(500),
            platform VARCHAR(50),
            status VARCHAR(20) DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            error_message TEXT,
            content TEXT
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(create_table_sql)

    async def create_task(self, task: TaskCreate) -> Task:
        """创建新任务"""
        now = datetime.now()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO tasks (task_id, video_url, platform, created_at, updated_at, status)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                task.task_id, task.video_url, task.platform, now, now, TaskStatus.PROCESSING
            )
        return self._record_to_task(record)

    async def get_task(self, task_id: str) -> Optional[Task]:
        """根据task_id获取任务"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM tasks WHERE task_id = $1", task_id
            )
        return self._record_to_task(record) if record else None

    async def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务"""
        updates = []
        values = []
        param_idx = 1

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1

        if not updates:
            return await self.get_task(task_id)

        updates.append("updated_at = NOW()")
        values.append(task_id)

        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ${param_idx}"

        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(sql, *values)
        return self._record_to_task(record) if record else None

    def _record_to_task(self, record) -> Task:
        """将数据库记录转换为Task对象"""
        return Task(
            id=record["id"],
            task_id=record["task_id"],
            video_url=record["video_url"],
            title=record["title"],
            platform=record["platform"],
            status=TaskStatus(record["status"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            completed_at=record["completed_at"],
            error_message=record["error_message"],
            content=record["content"]
        )

# 全局存储实例
storage = PostgresStorage()
