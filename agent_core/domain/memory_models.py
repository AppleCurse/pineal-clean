from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone
import uuid

class AgentRun(BaseModel):
    task_id: str
    agent_name: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_summary: Dict[str, Any] = {}
    output_summary: Dict[str, Any] = {}
    confidence: Optional[float] = None
    evidence_ids: List[str] = []
    warnings: List[str] = []
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(extra="allow")

class TaskSnapshot(BaseModel):
    task_id: str
    status: str = "initialized"  # initialized, processing, halted, completed, failed
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_agent: Optional[str] = None
    planned_agents: List[str] = []
    completed_agents: List[str] = []
    halted_reason: Optional[str] = None
    resonance_score: Optional[float] = None
    required_threshold: float = 0.70
    agent_runs: Dict[str, AgentRun] = {}
    evidence_chain: List[Dict[str, Any]] = []

    model_config = ConfigDict(extra="allow")

class ChatMessage(BaseModel):
    role: str  # user, aspasia
    content: str
    timestamp: datetime

class AspasiaSession(BaseModel):
    session_id: str
    client_id: str
    active_task_id: Optional[str] = None
    conversation_history: List[ChatMessage] = []
    referenced_evidence: List[str] = []

    @classmethod
    def create(cls, client_id: str) -> "AspasiaSession":
        return cls(
            session_id=str(uuid.uuid4()),
            client_id=client_id,
        )

    def add_message(self, role: str, content: str):
        self.conversation_history.append(
            ChatMessage(role=role, content=content, timestamp=datetime.now(timezone.utc))
        )
