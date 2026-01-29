import asyncpg
from typing import Optional, List
from datetime import datetime
from config.settings import settings
from models.task import (
    Task, TaskCreate, TaskStatus,
    LearningProgress, LearningStatus, ConceptMastery, ConceptStatus, LearningCheckpoint
)

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
        # 任务表
        create_tasks_table = """
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

        # 学习进度表
        create_learning_progress_table = """
        CREATE TABLE IF NOT EXISTS learning_progress (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'not_started',
            study_time INTEGER DEFAULT 0,
            questions_asked INTEGER DEFAULT 0,
            last_position TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, task_id)
        );
        """

        # 概念掌握表
        create_concept_mastery_table = """
        CREATE TABLE IF NOT EXISTS concept_mastery (
            id SERIAL PRIMARY KEY,
            progress_id INTEGER NOT NULL REFERENCES learning_progress(id) ON DELETE CASCADE,
            concept VARCHAR(200) NOT NULL,
            status VARCHAR(20) DEFAULT 'unknown',
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """

        # 学习检查点表
        create_learning_checkpoints_table = """
        CREATE TABLE IF NOT EXISTS learning_checkpoints (
            id SERIAL PRIMARY KEY,
            progress_id INTEGER NOT NULL REFERENCES learning_progress(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            position VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_tasks_table)
            await conn.execute(create_learning_progress_table)
            await conn.execute(create_concept_mastery_table)
            await conn.execute(create_learning_checkpoints_table)

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
        """根据task_id(UUID)获取任务"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM tasks WHERE task_id = $1", task_id
            )
        return self._record_to_task(record) if record else None

    async def get_task_by_id(self, id: int) -> Optional[Task]:
        """根据id(数据库自增ID)获取任务"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM tasks WHERE id = $1", id
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

    # ===== 学习进度相关方法 =====

    async def get_or_create_progress(self, user_id: str, task_id: int) -> LearningProgress:
        """获取或创建学习进度"""
        async with self.pool.acquire() as conn:
            # 尝试获取现有进度
            record = await conn.fetchrow(
                "SELECT * FROM learning_progress WHERE user_id = $1 AND task_id = $2",
                user_id, task_id
            )
            if record:
                return self._record_to_progress(record)

            # 创建新进度
            now = datetime.now()
            record = await conn.fetchrow(
                """
                INSERT INTO learning_progress (user_id, task_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                user_id, task_id, now, now
            )
            return self._record_to_progress(record)

    async def update_progress(self, progress_id: int, **kwargs) -> Optional[LearningProgress]:
        """更新学习进度"""
        updates = []
        values = []
        param_idx = 1

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1

        if not updates:
            async with self.pool.acquire() as conn:
                record = await conn.fetchrow(
                    "SELECT * FROM learning_progress WHERE id = $1", progress_id
                )
            return self._record_to_progress(record) if record else None

        updates.append("updated_at = NOW()")
        values.append(progress_id)

        sql = f"UPDATE learning_progress SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"

        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(sql, *values)
        return self._record_to_progress(record) if record else None

    async def get_user_progress_list(self, user_id: str) -> List[tuple[LearningProgress, Task]]:
        """获取用户的所有学习进度"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT
                    lp.id as lp_id, lp.user_id, lp.task_id as lp_task_id,
                    lp.status as lp_status, lp.study_time, lp.questions_asked,
                    lp.last_position, lp.created_at as lp_created_at, lp.updated_at as lp_updated_at,
                    t.id as t_id, t.task_id as t_task_id, t.video_url, t.title,
                    t.platform, t.status as t_status, t.created_at as t_created_at,
                    t.updated_at as t_updated_at, t.completed_at, t.error_message, t.content
                FROM learning_progress lp
                JOIN tasks t ON lp.task_id = t.id
                WHERE lp.user_id = $1
                ORDER BY lp.updated_at DESC
                """,
                user_id
            )

        result = []
        for record in records:
            progress = LearningProgress(
                id=record["lp_id"],
                user_id=record["user_id"],
                task_id=record["lp_task_id"],
                status=LearningStatus(record["lp_status"]),
                study_time=record["study_time"],
                questions_asked=record["questions_asked"],
                last_position=record["last_position"],
                created_at=record["lp_created_at"],
                updated_at=record["lp_updated_at"]
            )
            task = Task(
                id=record["t_id"],
                task_id=record["t_task_id"],
                video_url=record["video_url"],
                title=record["title"],
                platform=record["platform"],
                status=TaskStatus(record["t_status"]),
                created_at=record["t_created_at"],
                updated_at=record["t_updated_at"],
                completed_at=record["completed_at"],
                error_message=record["error_message"],
                content=record["content"]
            )
            result.append((progress, task))
        return result

    async def add_concept(self, progress_id: int, concept: str, status: ConceptStatus = ConceptStatus.UNKNOWN, notes: Optional[str] = None) -> ConceptMastery:
        """添加概念掌握记录"""
        now = datetime.now()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO concept_mastery (progress_id, concept, status, notes, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                progress_id, concept, status.value, notes, now, now
            )
        return self._record_to_concept(record)

    async def get_concepts_by_progress(self, progress_id: int) -> List[ConceptMastery]:
        """获取学习进度的所有概念"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT * FROM concept_mastery WHERE progress_id = $1 ORDER BY updated_at DESC",
                progress_id
            )
        return [self._record_to_concept(r) for r in records]

    async def save_checkpoint(self, progress_id: int, content: str, position: str) -> LearningCheckpoint:
        """保存学习检查点"""
        now = datetime.now()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO learning_checkpoints (progress_id, content, position, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                progress_id, content, position, now
            )
        return self._record_to_checkpoint(record)

    async def get_recent_tasks(self, limit: int = 10) -> List[Task]:
        """获取最近的任务列表"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT * FROM tasks WHERE status = 'completed' ORDER BY completed_at DESC LIMIT $1",
                limit
            )
        return [self._record_to_task(r) for r in records]

    def _record_to_progress(self, record) -> LearningProgress:
        """将数据库记录转换为LearningProgress对象"""
        return LearningProgress(
            id=record["id"],
            user_id=record["user_id"],
            task_id=record["task_id"],
            status=LearningStatus(record["status"]),
            study_time=record["study_time"],
            questions_asked=record["questions_asked"],
            last_position=record["last_position"],
            created_at=record["created_at"],
            updated_at=record["updated_at"]
        )

    def _record_to_concept(self, record) -> ConceptMastery:
        """将数据库记录转换为ConceptMastery对象"""
        return ConceptMastery(
            id=record["id"],
            progress_id=record["progress_id"],
            concept=record["concept"],
            status=ConceptStatus(record["status"]),
            notes=record["notes"],
            created_at=record["created_at"],
            updated_at=record["updated_at"]
        )

    def _record_to_checkpoint(self, record) -> LearningCheckpoint:
        """将数据库记录转换为LearningCheckpoint对象"""
        return LearningCheckpoint(
            id=record["id"],
            progress_id=record["progress_id"],
            content=record["content"],
            position=record["position"],
            created_at=record["created_at"]
        )

# 全局存储实例
storage = PostgresStorage()
