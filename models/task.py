from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class TaskStatus(str, Enum):
    PROCESSING = "processing"
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
    content: Optional[str] = Field(None, description="Processed content")

class TaskCreate(BaseModel):
    task_id: str
    video_url: str
    platform: Optional[str] = None

class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    content: Optional[str] = None
    completed_at: Optional[datetime] = None
