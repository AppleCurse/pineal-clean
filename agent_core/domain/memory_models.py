from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone
import uuid

class AgentRun(BaseModel):
    task_id: str
    agent_name: str
    status: str = "pending"  # pending, running, completed, failed, halted
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

# --- 360° BÜTÜNCÜL İNSAN PROFİLLEME MODELLERİ ---

class PassionProfile(BaseModel):
    """Kişinin neşe, yaratıcılık, entelektüel merak ve tutku duyduğu alanlar."""
    core_passions: List[str] = []
    energizing_topics: List[str] = []
    flow_triggers: List[str] = []
    sentiment_polarity: float = 0.0  # -1.0 (karamsar) ile +1.0 (coşkulu) arası
    evidence_quotes: List[str] = []
    confidence: float = 1.0

    model_config = ConfigDict(extra="allow")

class FrictionProfile(BaseModel):
    """Kişinin sınırları, hassasiyetleri, yorulma/tükenme ve şikayet noktaları."""
    sensitivities: List[str] = []
    stress_triggers: List[str] = []
    boundary_signals: List[str] = []
    evidence_quotes: List[str] = []
    confidence: float = 1.0

    model_config = ConfigDict(extra="allow")

class CognitiveStyle(BaseModel):
    """Kişinin düşünce kalıbı, iletişim üslubu ve sosyal ritmi."""
    communication_tone: str = "dengeli"  # doğrudan, analitik, metaforik, samimi, mesafeli
    complexity_level: str = "orta"  # sade, teknik, kavramsal
    humor_style: Optional[str] = None  # hiciv, ironi, kuru mizah, yok
    social_orientation: str = "bağımsız"  # toplulukçu, bağımsız, gözlemci
    confidence: float = 1.0

    model_config = ConfigDict(extra="allow")

class AuthenticBridge(BaseModel):
    """Kullanıcı ile hedef arasındaki sahici ortak değerler ve yapıcı iletişim köprüsü."""
    shared_passions: List[str] = []
    complementary_perspectives: List[str] = []
    resonance_score: float = 0.0  # 0.0 - 1.0
    authentic_opening_topic: str = ""
    conversation_starter_rationale: str = ""
    suggested_opening_message: str = ""
    confidence: float = 1.0

    model_config = ConfigDict(extra="allow")

class HolisticProfile(BaseModel):
    """360 derece tam insan profili."""
    username: str
    passions: Optional[PassionProfile] = None
    frictions: Optional[FrictionProfile] = None
    cognitive: Optional[CognitiveStyle] = None
    bridge: Optional[AuthenticBridge] = None
    verified_claims: List[Dict[str, Any]] = []
    overall_confidence: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(extra="allow")

# --- GÖREV VE TELEMETRİ SNAPSHOT MODELLERİ ---

class TaskSnapshot(BaseModel):
    task_id: str
    status: str = "initialized"  # initialized, processing, halted_evidence, halted_frequency, completed, failed
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
    holistic_profile: Optional[HolisticProfile] = None

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
