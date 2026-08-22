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
        visual_evidence = payload.get("visual_evidence", {})
        
        posts_text = "\n".join([f"- {p}" for p in posts[:10]]) if posts else "Gönderi metni bulunamadı."
        visual_text = f"""
Görsel İnceleme Kanıtları (Multimodal Vision):
- Tespit Edilen Somut Nesneler: {visual_evidence.get('detected_objects', [])}
- Mekanlar ve Ortam: {visual_evidence.get('environment_and_places', [])}
- Estetik ve Görsel Dil: {visual_evidence.get('aesthetic_style', '')}
- Yapılan Eylemler: {visual_evidence.get('activity_signals', [])}
- Görsel Özeti: {visual_evidence.get('visual_evidence_summary', '')}
""" if visual_evidence else "Görsel kanıt bulunamadı."

        if not bio and not posts and not visual_evidence:
            return PassionProfile(
                core_passions=[],
                energizing_topics=[],
                flow_triggers=[],
                sentiment_polarity=0.0,
                evidence_quotes=[],
                confidence=0.2
            )

        prompt = f"""
Aşağıdaki sosyal medya profil verilerini ve fotoğraflardan çıkarılan SOMUT görsel kanıtları incele.
Bu kişinin GERÇEKTE neye tutku duyduğunu, hangi konuların ve eylemlerin onu motive ettiğini analiz et.
Asla genel geçer astroloji veya kişisel gelişim genellemeleri yapma. 
Yalnızca verilen metinlerdeki ve fotoğraflarda fiilen tespit edilen somut nesne/mekan delillerine dayan.

Hedef Biyografi:
"{bio}"

Son Paylaşımlar / Metinler:
{posts_text}

{visual_text}

Aşağıdaki JSON şemasına birebir uygun yanıt ver:
{{
  "core_passions": ["Kişinin somut paylaşımlarından ve fotoğraflarından kanıtlanan 1-3 ana tutku alanı"],
  "energizing_topics": ["Konuşmaktan, üretmekten veya görselleştirmekten keyif aldığı spesifik konular"],
  "flow_triggers": ["Onu üretken veya coşkulu kılan somut tetikleyiciler"],
  "sentiment_polarity": 0.6, // -1.0 (karamsar) ile +1.0 (coşkulu) arası float
  "evidence_quotes": ["Metinden veya görsel kanıttan doğrudan alıntılanan somut detaylar"],
  "confidence": 0.90
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
