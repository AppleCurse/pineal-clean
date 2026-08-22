import logging
from typing import Dict, Any, Optional
from agent_core.domain.memory_models import PassionProfile
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

class PassionMapperAgent:
    """
    Hedefin neşe, yaratıcılık, tutku ve entelektüel ilgi alanlarını 
    somut paylaşımlarından ve dilinden haritalandıran ajan.
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()

    async def execute(self, payload: Dict[str, Any]) -> PassionProfile:
        target = payload.get("target_profile", {})
        bio = target.get("bio", "")
        posts = target.get("posts", [])
        
        posts_text = "\n".join([f"- {p}" for p in posts[:10]]) if posts else "Gönderi metni bulunamadı."
        
        if not bio and not posts:
            return PassionProfile(
                core_passions=[],
                energizing_topics=[],
                flow_triggers=[],
                sentiment_polarity=0.0,
                evidence_quotes=[],
                confidence=0.2
            )

        prompt = f"""
Aşağıdaki sosyal medya profil verilerini incele.
Bu kişinin GERÇEKTE neye tutku duyduğunu, hangi konuların onu neşelendirdiğini ve motive ettiğini analiz et.
Asla basmakalıp astroloji genellemeleri yapma. Yalnızca verilen metinlerdeki somut delillere dayan.

Hedef Biyografi:
"{bio}"

Son Paylaşımlar / Metinler:
{posts_text}

Aşağıdaki JSON şemasına birebir uygun yanıt ver:
{{
  "core_passions": ["Kişinin en çok heyecan duyduğu 1-3 ana alan"],
  "energizing_topics": ["Konuşmaktan veya paylaşmaktan keyif aldığı spesifik konular"],
  "flow_triggers": ["Onu üretken veya coşkulu kılan tetikleyiciler"],
  "sentiment_polarity": 0.5, // -1.0 (karamsar) ile +1.0 (coşkulu) arası float
  "evidence_quotes": ["Metinden doğrudan alıntılanan 1-2 somut cümle"],
  "confidence": 0.85
}}
"""
        try:
            result = await self.llm_gateway.query_json(
                prompt=prompt,
                schema=PassionProfile,
                temperature=0.3,
                tier=1
            )
            return result
        except Exception as e:
            logger.warning(f"PassionMapper LLM hatası: {e}")
            return PassionProfile(
                core_passions=["Genel İletişim"],
                energizing_topics=[],
                flow_triggers=[],
                sentiment_polarity=0.0,
                evidence_quotes=[],
                confidence=0.3
            )
