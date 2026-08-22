import logging
from typing import Dict, Any, Optional
from agent_core.domain.memory_models import FrictionProfile
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

class FrictionDetectorAgent:
    """
    Hedefin sınırlarını, hassasiyetlerini, yorulma/şikayet noktalarını
    ve mesafeli durduğu durumları saygılı ve kanıta dayalı analiz eden ajan.
    (Amaç açık aramak değil, sınırları bilip saygı duymaktır).
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()

    async def execute(self, payload: Dict[str, Any]) -> FrictionProfile:
        target = payload.get("target_profile", {})
        bio = target.get("bio", "")
        posts = target.get("posts", [])
        
        posts_text = "\n".join([f"- {p}" for p in posts[:10]]) if posts else "Gönderi metni bulunamadı."
        
        if not bio and not posts:
            return FrictionProfile(
                sensitivities=[],
                stress_triggers=[],
                boundary_signals=[],
                evidence_quotes=[],
                confidence=0.2
            )

        prompt = f"""
Aşağıdaki profil verilerini incele.
Bu kişinin iletişimde nelere mesafe koyduğunu, nelere karşı hassas veya eleştirel olduğunu,
nelerin onu yorup rahatsız edebileceğini tespit et.
Asla sahte derin travmalar uydurma. Sadece metinlerdeki gerçek sınırları ve hassasiyetleri bul.

Hedef Biyografi:
"{bio}"

Son Paylaşımlar / Metinler:
{posts_text}

Aşağıdaki JSON şemasına birebir uygun yanıt ver:
{{
  "sensitivities": ["Kişinin hoşlanmadığı, mesafeli durduğu veya hassas olduğu konular"],
  "stress_triggers": ["Onu yoran, tepkisini çeken durumlar"],
  "boundary_signals": ["İletişimde aşılmaması gereken kişisel sınırlar"],
  "evidence_quotes": ["Metinden doğrudan alıntılanan 1-2 kanıt cümlesi"],
  "confidence": 0.80
}}
"""
        try:
            result = await self.llm_gateway.query_json(
                prompt=prompt,
                schema=FrictionProfile,
                temperature=0.3,
                tier=1
            )
            return result
        except Exception as e:
            logger.warning(f"FrictionDetector LLM hatası: {e}")
            return FrictionProfile(
                sensitivities=["Saygısızlık"],
                stress_triggers=[],
                boundary_signals=[],
                evidence_quotes=[],
                confidence=0.3
            )
