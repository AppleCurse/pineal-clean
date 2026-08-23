from pydantic import BaseModel, ConfigDict
from typing import Dict

class MirrorReflection(BaseModel):
    user_core_frequency: str  # Kullanıcının gerçek frekansı
    surface_persona: str      # Dışarıya yansıttığı
    alignment_score: float      # Uyum skoru (0-1)
    authentic_anchors: list   # Gerçekliğin sabit noktaları
    confidence: float = 0.9
    
    model_config = ConfigDict(extra="forbid")

class MirrorOfTruth:
    """
    Kullanıcının kendine ayna tutması.
    Yüzey vs. Öz ayrımı.
    """
    
    async def execute(self, input_data: Dict, memory, llm_gateway) -> MirrorReflection:
        import logging
        log = logging.getLogger(__name__)

        user_data = input_data.get('user_profile', {})
        user_ctx = input_data.get('user_context', {})
        sacred_rules = input_data.get('sacred_rules', "")

        merged_user = {
            'private_rituals': user_data.get('private_rituals') or ([user_ctx.get('rituals')] if isinstance(user_ctx.get('rituals'), str) else user_ctx.get('rituals', [])),
            'late_night_playlist': user_data.get('late_night_playlist') or ([user_ctx.get('playlist')] if isinstance(user_ctx.get('playlist'), str) else user_ctx.get('playlist', [])),
            'secret_envies': user_data.get('secret_envies') or ([user_ctx.get('envies')] if isinstance(user_ctx.get('envies'), str) else user_ctx.get('envies', []))
        }

        core_freq = self._extract_core_frequency(merged_user)
        anchors = self._find_anchors(merged_user)

        prompt = (
            f"Sen 'Mirror of Truth' ajanısın. Görevin, verilen kullanıcı verisinden yüzey kimliğini ve gerçek (core) frekansı bulmak.\n"
            f"Kullanıcı Verisi:\n"
            f"Ritüeller: {merged_user.get('private_rituals')}\n"
            f"Müzik: {merged_user.get('late_night_playlist')}\n"
            f"Kıskançlık/Arzu: {merged_user.get('secret_envies')}\n\n"
            f"GERÇEK METRİKLER (NLP ile Çıkarılmış Frekans ve Çapalar):\n"
            f"- Algoritmik Kök Frekans Sinyali: {core_freq}\n"
            f"- NLP Tabanlı Sabit Noktalar (Anchors): {anchors}\n\n"
            f"{sacred_rules}\n"
            f"Şimdi bu verileri analiz et ve beklenen JSON formatında çıktı üret."
        )

        try:
            return await llm_gateway.query_json(prompt, MirrorReflection)
        except Exception as e:
            log.warning("MirrorOfTruth: LLM atlandı, deterministik fallback kullanılıyor: %s", e)
            # Deterministik fallback — data_confidence=False ile işaretlendi
            return MirrorReflection(
                user_core_frequency=core_freq,
                surface_persona="bilinmiyor_llm_kapali",
                alignment_score=0.5,
                authentic_anchors=anchors,
                confidence=0.1,  # Düşük güven: LLM verisi yok
            )
    def _calculate_alignment(self, surface: str, core: str, user_data: Dict) -> float:
        return user_data.get('authenticity_score', 0.8) if isinstance(user_data, dict) else 0.8
    
    def _extract_core_frequency(self, user_data: Dict) -> str:
        """
        Kullanıcının yalnız kaldığında yaptığı eylemlerden dinamik frekans analizi
        """
        import re
        from collections import Counter
        
        rituals = " ".join(user_data.get('private_rituals', [])).lower()
        music = " ".join(user_data.get('late_night_playlist', [])).lower()
        envy = " ".join(user_data.get('secret_envies', [])).lower()
        
        text = f"{rituals} {music} {envy}"
        words = [w for w in re.findall(r'\b\w+\b', text) if len(w) > 3]
        
        if not words:
            return "belirsiz_frekans"
            
        common = Counter(words).most_common(3)
        return "_".join([w for w, c in common])
    
    def _find_anchors(self, user_data: Dict) -> list:
        """
        Dinamik anchor (sabit nokta) tespiti - NLP ile
        """
        import re
        from collections import Counter
        
        rituals = " ".join(user_data.get('private_rituals', [])).lower()
        words = [w for w in re.findall(r'\b\w+\b', rituals) if len(w) > 4]
        
        if not words:
            return ["bilinmeyen_caba"]
            
        return [w + "_anchor" for w, c in Counter(words).most_common(3)]
