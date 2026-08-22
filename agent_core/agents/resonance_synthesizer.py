import logging
from typing import Dict, Any, Optional
from agent_core.domain.memory_models import AuthenticBridge
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

class ResonanceSynthesizerAgent:
    """
    Kullanıcının profili/değerleri ile hedefin tutkularını, hassasiyetlerini
    ve iletişim tonunu sentezleyerek sahici, yapıcı ve derin bir diyalog köprüsü kuran ajan.
    (Manipülatif kanca yerine karşılıklı değer ve saygı üreten ilk temas).
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()

    async def execute(self, payload: Dict[str, Any]) -> AuthenticBridge:
        user_profile = payload.get("user_profile", {})
        passions_data = payload.get("passions", {})
        friction_data = payload.get("frictions", {})
        cognitive_data = payload.get("cognitive", {})
        sacred_rules = payload.get("sacred_rules", "")

        user_bio = user_profile.get("bio", "Analitik gözlemci.")
        user_posts = user_profile.get("posts", [])
        user_context = f"Kullanıcı Biyografisi: {user_bio}\nKullanıcı Paylaşımları: {', '.join(user_posts)}"

        target_context = f"""
Hedefin Tutkuları: {passions_data}
Hedefin Hassasiyetleri ve Sınırları: {friction_data}
Hedefin İletişim Üslubu: {cognitive_data}
"""

        prompt = f"""
Aşağıda iki insanın profili verilmiştir: (1) Kullanıcı, (2) Hedef Kişi.
Amacımız ucuz bir manipülasyon yapmak DEĞİLDİR.
Amacımız: İki profil arasındaki GERÇEK ortak heyecanları, birbirini tamamlayan bakış açılarını bulmak
ve karşı tarafın sınırlarına saygı duyan, sahici ve derinlikli bir ilk sohbet başlatıcı oluşturmaktır.

{user_context}

{target_context}

Özel İletişim Kuralları:
"{sacred_rules}"

Aşağıdaki JSON formatında yanıt ver:
{{
  "shared_passions": ["Her iki tarafın da ortak ilgi duyduğu veya rezonans kurabileceği 1-3 konu"],
  "complementary_perspectives": ["Birbirini zenginleştirebilecek farklı bakış açıları"],
  "resonance_score": 0.85, // 0.0 ile 1.0 arası genel sahici uyum skoru
  "authentic_opening_topic": "İletişimin başlayacağı en doğal ve derinlikli konu başlığı",
  "conversation_starter_rationale": "Neden bu konunun seçildiğinin mantıksal ve saygılı açıklaması",
  "suggested_opening_message": "Doğrudan karşı tarafa gönderilebilecek, samimi, merak uyandırıcı ve saygılı mesaj taslağı",
  "confidence": 0.90
}}
"""
        try:
            result = await self.llm_gateway.query_json(
                prompt=prompt,
                schema=AuthenticBridge,
                temperature=0.4,
                tier=1
            )
            return result
        except Exception as e:
            logger.warning(f"ResonanceSynthesizer LLM hatası: {e}")
            return AuthenticBridge(
                shared_passions=["Genel İletişim"],
                complementary_perspectives=[],
                resonance_score=0.5,
                authentic_opening_topic="Ortak İlgi Alanları",
                conversation_starter_rationale="Fallback",
                suggested_opening_message="Merhaba, paylaşımlarınızdaki bakış açısı dikkatimi çekti.",
                confidence=0.4
            )
