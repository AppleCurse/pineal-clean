"""
PINEAL-HERETIC v5.0 - Agent Status Tracker
12 ajanin Ready/Active/Wait/Error/Done durumlarini Redis Pub/Sub uzerinden
anlik yayinlayan ve Agent Rack slotlarini besleyen izleyici.
"""
import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from enum import Enum

from .redis_bus import get_redis_bus, RedisBus

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    WAIT = "Wait"
    READY = "Ready"
    ACTIVE = "Active"
    DONE = "Done"
    ERROR = "Error"


# 12 ajan tanimi - Docker Compose'da bagimsiz servis olacaklar
AGENT_DEFINITIONS = [
    {"id": "mirror_truth", "name": "MIRROR TRUTH", "color": "#10b981", "glyph": "🪞", "tier": 1},
    {"id": "autonomous_verifier", "name": "AUTONOMOUS VERIFIER", "color": "#a855f7", "glyph": "⚖️", "tier": 1},
    {"id": "human_behavior", "name": "HUMAN BEHAVIOR", "color": "#f59e0b", "glyph": "👤", "tier": 1},
    {"id": "passion_mapper", "name": "PASSION MAPPER", "color": "#f59e0b", "glyph": "✨", "tier": 2},
    {"id": "friction_detector", "name": "FRICTION & BOUNDS", "color": "#ef4444", "glyph": "🛡️", "tier": 2},
    {"id": "cognitive_profiler", "name": "COGNITIVE PROFILER", "color": "#06b6d4", "glyph": "🧠", "tier": 2},
    {"id": "resonance_calculator", "name": "RESONANCE CALCULATOR", "color": "#3b82f6", "glyph": "📐", "tier": 2},
    {"id": "pattern_interrupt", "name": "PATTERN INTERRUPT", "color": "#dc2626", "glyph": "💥", "tier": 3},
    {"id": "osint_investigator", "name": "OSINT INVESTIGATOR", "color": "#8b5cf6", "glyph": "🔍", "tier": 3},
    {"id": "authenticity_auditor", "name": "AUTHENTICITY AUDITOR", "color": "#14b8a6", "glyph": "🔎", "tier": 1},
    {"id": "depth_analyst", "name": "DEPTH ANALYST", "color": "#eab308", "glyph": "🕳️", "tier": 2},
    {"id": "resonance_synthesizer", "name": "RESONANCE SYNTHESIZER", "color": "#ec4899", "glyph": "🎼", "tier": 3},
]


class AgentStatusTracker:
    """
    Ajan durumlarini izler, Redis'e yayinlar, WebSocket koprusune aktarir.
    Docker Compose altinda her ajan bagimsiz servis gibi davranir ama
    bu tracker merkezi durumu toplar.
    """

    def __init__(self, redis_bus: Optional[RedisBus] = None):
        self.redis_bus = redis_bus or get_redis_bus()
        self._statuses: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        # Baslangicta hepsi Wait
        for agent in AGENT_DEFINITIONS:
            self._statuses[agent["id"]] = {
                "agent_id": agent["id"],
                "name": agent["name"],
                "status": AgentStatus.WAIT.value,
                "color": agent["color"],
                "glyph": agent["glyph"],
                "tier": agent["tier"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {},
            }

    async def update_status(self, agent_id: str, status: str, metadata: Optional[Dict] = None):
        async with self._lock:
            if agent_id not in self._statuses:
                # Bilinmeyen ajan - dinamik ekle
                self._statuses[agent_id] = {
                    "agent_id": agent_id,
                    "name": agent_id.upper(),
                    "status": status,
                    "color": "#6b7280",
                    "glyph": "🤖",
                    "tier": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": metadata or {},
                }
            else:
                self._statuses[agent_id]["status"] = status
                self._statuses[agent_id]["timestamp"] = datetime.now(timezone.utc).isoformat()
                if metadata:
                    self._statuses[agent_id]["metadata"] = metadata

            # Redis'e yayinla
            try:
                await self.redis_bus.publish_agent_status(agent_id, status, metadata)
            except Exception as e:
                logger.debug(f"Redis publish hatasi {agent_id}: {e}")

            logger.info(f"Agent {agent_id} -> {status}")
            return self._statuses[agent_id]

    async def set_ready(self, agent_id: str):
        return await self.update_status(agent_id, AgentStatus.READY.value)

    async def set_active(self, agent_id: str, task_id: Optional[str] = None):
        meta = {"task_id": task_id} if task_id else {}
        return await self.update_status(agent_id, AgentStatus.ACTIVE.value, meta)

    async def set_done(self, agent_id: str, result_summary: Optional[str] = None):
        meta = {"result": result_summary} if result_summary else {}
        return await self.update_status(agent_id, AgentStatus.DONE.value, meta)

    async def set_error(self, agent_id: str, error: str):
        return await self.update_status(agent_id, AgentStatus.ERROR.value, {"error": error})

    async def set_wait(self, agent_id: str):
        return await self.update_status(agent_id, AgentStatus.WAIT.value)

    async def set_all_ready(self):
        for agent in AGENT_DEFINITIONS:
            await self.set_ready(agent["id"])

    async def set_all_wait(self):
        for agent in AGENT_DEFINITIONS:
            await self.set_wait(agent["id"])

    def get_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._statuses.get(agent_id)

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._statuses)

    def get_status_list(self):
        """Frontend icin liste formati"""
        return list(self._statuses.values())

# Global singleton
_tracker: Optional[AgentStatusTracker] = None


def get_tracker() -> AgentStatusTracker:
    global _tracker
    if _tracker is None:
        _tracker = AgentStatusTracker()
    return _tracker


async def init_tracker(redis_url: Optional[str] = None) -> AgentStatusTracker:
    global _tracker
    from .redis_bus import init_redis_bus
    bus = await init_redis_bus(redis_url)
    _tracker = AgentStatusTracker(bus)
    # Ajanlar baslangicta beklemede (Wait); sahte Ready durumu uretilmez
    await _tracker.set_all_wait()
    return _tracker
