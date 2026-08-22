import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field

class Severity(str, Enum):
    Info = "Info"
    Warning = "Warning"
    High = "High"
    Critical = "Critical"

class AgentEventType(str, Enum):
    TaskStarted = "TaskStarted"
    StepCompleted = "StepCompleted"
    ErrorHalt = "ErrorHalt"
    AwaitingHuman = "AwaitingHuman"
    TaskCompleted = "TaskCompleted"
    FrequencyUpdate = "FrequencyUpdate"
    GenericLog = "GenericLog"

# Using discriminated unions for precise schema mirroring Rust's AgentEvent enum
class BaseAgentEvent(BaseModel):
    event_type: AgentEventType

class TaskStartedEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.TaskStarted
    task_id: str
    agent_name: str
    input_summary: str

class StepCompletedEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.StepCompleted
    task_id: str
    agent_name: str
    step_name: str
    output_hash: str

class ErrorHaltEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.ErrorHalt
    task_id: str
    agent_name: str
    error_code: str
    error_message: str
    severity: Severity

class AwaitingHumanEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.AwaitingHuman
    task_id: str
    agent_name: str
    reason: str
    options: List[str]

class TaskCompletedEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.TaskCompleted
    task_id: str
    agent_name: str
    final_result_hash: str
    duration_ms: int

class FrequencyUpdateEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.FrequencyUpdate
    task_id: str
    alignment_score: float
    authentic_anchor_count: int
    overall_frequency: str

class GenericLogEvent(BaseAgentEvent):
    event_type: AgentEventType = AgentEventType.GenericLog
    message: str
    level: str = "INFO"

AgentEvent = Union[
    TaskStartedEvent,
    StepCompletedEvent,
    ErrorHaltEvent,
    AwaitingHumanEvent,
    TaskCompletedEvent,
    FrequencyUpdateEvent,
    GenericLogEvent
]

class TelemetryEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event: AgentEvent
    correlation_id: Optional[str] = None
