import logging
from typing import Dict, Any, Optional
from agent_core.domain.memory_models import FrictionProfile
from agent_core.services.llm_gateway import LLMGateway
from agent_core.agents.target_psyche_profiler import TargetPsycheProfiler

logger = logging.getLogger(__name__)

class FrictionDetectorAgent(TargetPsycheProfiler):
    """
    Hedefin sınırlarını, hassasiyetlerini, yorulma/şikayet noktalarını
    ve mesafeli durduğu durumları saygılı ve kanıta dayalı analiz eden ajan.
    (TargetPsycheProfiler omurgasına bağlı sürtünme lensi).
    """

    async def execute(self, payload: Dict[str, Any]) -> FrictionProfile:
        return await self.profile_frictions(payload)

