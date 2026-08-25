import logging
from typing import Dict, Any, Optional
from agent_core.domain.memory_models import CognitiveStyle
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

class CognitiveProfilerAgent:
    """
    Hedefin dilbilimsel tonunu, iletişim üslubunu, karmaşıklık düzeyini
    ve sosyal yaklaşımını metinlerinden analiz eden ajan.
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()

    async def execute(self, payload: Dict[str, Any]) -> CognitiveStyle:
        target = payload.get("target_profile", {})
        bio = target.get("bio", "")
        posts = target.get("posts", [])
        visual_evidence = payload.get("visual_evidence", {})
        
        posts_text = "\n".join([f"- {p}" for p in posts[:10]]) if posts else "Gönderi metni bulunamadı."
        visual_style = visual_evidence.get('aesthetic_style', '') if visual_evidence else ''
        visual_text = f"Fotoğraflardaki Görsel ve Estetik Dil: {visual_style}" if visual_style else ""

        if not bio and not posts and not visual_evidence:
            return CognitiveStyle(
                communication_tone="",
                complexity_level="",
                humor_style=None,
                social_orientation="",
                confidence=0.0,
                data_confidence=False,
                fallback_reason="no_target_data"
            )

        prompt = f"""
Aşağıdaki metinlerin dilbilimsel üslubunu, iletişim ritmini ve fotoğrafların estetik dilini incele.
Kişinin nasıl bir iletişim tarzı benimsediğini analiz et.

Hedef Biyografi:
"{bio}"

Son Paylaşımlar / Metinler:
{posts_text}

{visual_text}

Confidence kuralı: confidence alanını yalnızca verilen doğrudan kanıtın tamlığına göre 0.0 ile 1.0 arasında ölç; kanıt yetersizse 0.0 ve data_confidence=false döndür.

Aşağıdaki JSON şemasına birebir uygun yanıt ver:
{{
  "communication_tone": "doğrudan | analitik | samimi | mesafeli | metaforik",
  "complexity_level": "sade | teknik | kavramsal",
  "humor_style": "ironi | hiciv | kuru mizah | yok",
  "social_orientation": "toplulukçu | bağımsız | gözlemci",
  "confidence": 0.0
}}
"""
        try:
            result = await self.llm_gateway.query_json_chain(
                prompt=prompt,
                schema=CognitiveStyle,
                task="depth",
                temperature=0.3,
                agent_name="cognitive_profiler"
            )
            return result.model_copy(update={"data_confidence": True, "fallback_reason": None})
        except Exception as e:
            logger.warning(f"CognitiveProfiler LLM hatası: {e}")
            return CognitiveStyle(
                communication_tone="",
                complexity_level="",
                humor_style=None,
                social_orientation="",
                confidence=0.0,
                data_confidence=False,
                fallback_reason="llm_unavailable"
            )
