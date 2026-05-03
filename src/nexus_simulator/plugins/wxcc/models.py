"""
WXCC Simulator Models

Pydantic models for the Webex Contact Center simulator API.
These models match the real WXCC API response formats.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ==========================================
# Enums
# ==========================================

class TaskStatusEnum(str, Enum):
    """Task status values"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    TRANSFERRED = "transferred"


class TaskDirectionEnum(str, Enum):
    """Task direction values"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ChannelTypeEnum(str, Enum):
    """Channel type values"""
    TELEPHONY = "telephony"
    CHAT = "chat"
    EMAIL = "email"
    SOCIAL = "social"


class CallTypeEnum(str, Enum):
    """Call type values"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    CALLBACK = "callback"


# ==========================================
# Task Models (matching real WXCC API)
# ==========================================

class TaskAttributes(BaseModel):
    """Task attributes nested object"""
    status: TaskStatusEnum = Field(default=TaskStatusEnum.COMPLETED)
    direction: TaskDirectionEnum = Field(default=TaskDirectionEnum.INBOUND)
    origin: str = Field(default="", description="Caller phone number")
    destination: str = Field(default="", description="Called phone number")
    queueId: str | None = Field(None, description="Queue ID")
    queueName: str | None = Field(None, description="Queue name")
    agentId: str | None = Field(None, description="Agent ID")
    agentName: str | None = Field(None, description="Agent name")
    wrapUpCode: str | None = Field(None, description="Wrap up code")
    ani: str | None = Field(None, description="ANI (Automatic Number Identification)")
    dnis: str | None = Field(None, description="DNIS (Dialed Number Identification Service)")

    class Config:
        use_enum_values = True


class Task(BaseModel):
    """Task model matching real WXCC task structure"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    taskName: str = Field(default="Inbound Call")
    channelType: ChannelTypeEnum = Field(default=ChannelTypeEnum.TELEPHONY)
    startTime: str = Field(description="ISO format timestamp")
    endTime: str | None = Field(None, description="ISO format timestamp")
    createdTime: int | None = Field(None, description="Timestamp in milliseconds")
    lastUpdatedTime: int | None = Field(None, description="Timestamp in milliseconds")
    attributes: TaskAttributes = Field(default_factory=TaskAttributes)

    class Config:
        use_enum_values = True


class TasksResponse(BaseModel):
    """Response model for GET /tasks endpoint"""
    data: list[Task] = Field(default_factory=list)
    meta: dict[str, Any] | None = Field(default_factory=dict)
    links: list[dict[str, str]] = Field(default_factory=list)


# ==========================================
# Recording Models (matching real WXCC API)
# ==========================================

class RecordingAttributes(BaseModel):
    """Recording attributes nested object"""
    fileName: str = Field(default="recording.wav")
    filePath: str = Field(description="URL to download recording")
    startTime: int = Field(description="Timestamp in milliseconds")
    stopTime: int = Field(description="Timestamp in milliseconds")
    participants: list[str] = Field(default_factory=list)
    channel1: str | None = Field(None, description="Channel 1 identifier")
    channel2: str | None = Field(None, description="Channel 2 identifier")
    callType: CallTypeEnum = Field(default=CallTypeEnum.INBOUND)

    class Config:
        use_enum_values = True


class Recording(BaseModel):
    """Recording model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attributes: RecordingAttributes


class TaskRecording(BaseModel):
    """Task with recordings container"""
    taskId: str
    recording: list[Recording] = Field(default_factory=list)


class CapturesQueryRequest(BaseModel):
    """Request body for POST /captures/query"""
    query: dict[str, list[str]] = Field(description="Query with taskIds")

    @property
    def task_ids(self) -> list[str]:
        """Extract task IDs from query"""
        return self.query.get("taskIds", [])


class CapturesResponse(BaseModel):
    """Response model for POST /captures/query endpoint"""
    data: list[TaskRecording] = Field(default_factory=list)
    meta: dict[str, Any] | None = Field(default_factory=dict)


# ==========================================
# Admin API Models (for simulator management)
# ==========================================

class CreateTaskRequest(BaseModel):
    """Request to create a mock task"""
    task_name: str = Field(default="Inbound Call", description="Task display name")
    channel_type: ChannelTypeEnum = Field(default=ChannelTypeEnum.TELEPHONY)
    status: TaskStatusEnum = Field(default=TaskStatusEnum.COMPLETED)
    direction: TaskDirectionEnum = Field(default=TaskDirectionEnum.INBOUND)
    origin: str = Field(default="+6512345678", description="Caller phone number")
    destination: str = Field(default="+6587654321", description="Called phone number")
    duration_seconds: int = Field(default=300, description="Call duration in seconds")
    queue_id: str | None = Field(None)
    queue_name: str | None = Field(None)
    agent_id: str | None = Field(None)
    agent_name: str | None = Field(None)
    recording_file: str | None = Field(None, description="S3 key for recording file")

    class Config:
        use_enum_values = True


class UpdateTaskRequest(BaseModel):
    """Request to update a mock task"""
    task_name: str | None = None
    status: TaskStatusEnum | None = None
    direction: TaskDirectionEnum | None = None
    origin: str | None = None
    destination: str | None = None
    end_time: str | None = None
    queue_id: str | None = None
    agent_id: str | None = None
    recording_file: str | None = None

    class Config:
        use_enum_values = True


class UploadRecordingRequest(BaseModel):
    """Request to associate a recording with a task"""
    task_id: str = Field(description="Task ID to associate recording with")
    file_name: str = Field(default="recording.wav")
    s3_key: str | None = Field(None, description="Existing S3 key if uploading separately")
    participants: list[str] = Field(default_factory=list)
    call_type: CallTypeEnum = Field(default=CallTypeEnum.INBOUND)

    class Config:
        use_enum_values = True


class SeedDataRequest(BaseModel):
    """Request to seed simulator with sample data"""
    num_tasks: int = Field(default=10, ge=1, le=100, description="Number of tasks to create")
    include_recordings: bool = Field(default=True, description="Include mock recordings")
    days_back: int = Field(default=7, ge=0, le=30, description="Spread tasks over this many days")
    use_current_time: bool = Field(default=False, description="Create all tasks with current timestamp (ignores days_back)")
    org_id: str | None = Field(None, description="Organization ID to use")


class AdminResponse(BaseModel):
    """Generic admin response"""
    success: bool = True
    message: str
    data: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SimulatorStatus(BaseModel):
    """Simulator status response"""
    enabled: bool
    org_id: str
    bucket: str
    prefix: str
    task_count: int
    recording_count: int
    last_updated: datetime | None = None


# ==========================================
# Error Models (matching WXCC error format)
# ==========================================

class WXCCErrorMessage(BaseModel):
    """WXCC error message detail"""
    description: str


class WXCCError(BaseModel):
    """WXCC error response format"""
    key: str = Field(description="Error code (e.g., '401', '404')")
    message: list[WXCCErrorMessage] = Field(default_factory=list)


class WXCCErrorResponse(BaseModel):
    """Error response matching WXCC format"""
    error: WXCCError


# ==========================================
# Internal Storage Models
# ==========================================

class StoredTask(BaseModel):
    """Internal task storage with additional metadata"""
    task: Task
    recording_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StoredRecording(BaseModel):
    """Internal recording storage with S3 reference"""
    recording: Recording
    task_id: str
    s3_key: str
    file_size: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimulatorData(BaseModel):
    """Complete simulator data structure for S3 storage"""
    org_id: str
    tasks: dict[str, StoredTask] = Field(default_factory=dict)
    recordings: dict[str, StoredRecording] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

