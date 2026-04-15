from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class TaskStatus(str, Enum):
    PROCESSING = "processing"
    DIGESTING = "digesting"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: Optional[int] = None
    task_id: str = Field(..., description="UUID for the task")
    video_url: str = Field(..., description="Video URL")
    title: Optional[str] = Field(None, description="Video title")
    platform: Optional[str] = Field(None, description="Video platform (douyin/bilibili)")
    status: TaskStatus = Field(default=TaskStatus.PROCESSING, description="Task status")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = Field(None, description="Error message if failed")
    content: Optional[str] = Field(None, description="Processed content (optimized by LLM)")
    raw_transcript: Optional[str] = Field(None, description="Raw transcription from audio (complete, unprocessed)")
    wiki_paths: Optional[str] = Field(None, description="JSON array of wiki note paths")

class TaskCreate(BaseModel):
    task_id: str
    video_url: str
    platform: Optional[str] = None

class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    content: Optional[str] = None
    raw_transcript: Optional[str] = None
    wiki_paths: Optional[str] = None
    completed_at: Optional[datetime] = None

# 学习进度相关模型
class LearningStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWING = "reviewing"

class ConceptStatus(str, Enum):
    UNKNOWN = "unknown"
    FAMILIAR = "familiar"
    UNDERSTOOD = "understood"
    MASTERED = "mastered"

class LearningProgress(BaseModel):
    id: Optional[int] = None
    user_id: str = Field(..., description="Telegram user ID")
    task_id: int = Field(..., description="Associated task ID")
    status: LearningStatus = Field(default=LearningStatus.NOT_STARTED)
    study_time: int = Field(default=0, description="Total study time in seconds")
    questions_asked: int = Field(default=0, description="Number of questions asked")
    last_position: Optional[str] = Field(None, description="Last reading position")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ConceptMastery(BaseModel):
    id: Optional[int] = None
    progress_id: int = Field(..., description="Associated learning progress ID")
    concept: str = Field(..., description="Concept name")
    status: ConceptStatus = Field(default=ConceptStatus.UNKNOWN)
    notes: Optional[str] = Field(None, description="User notes")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class LearningCheckpoint(BaseModel):
    id: Optional[int] = None
    progress_id: int = Field(..., description="Associated learning progress ID")
    content: str = Field(..., description="Checkpoint content/summary")
    position: str = Field(..., description="Position in the article")
    created_at: Optional[datetime] = None
