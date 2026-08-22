from pydantic import BaseModel, ConfigDict
from typing import Dict, Any

class MirrorReflection(BaseModel):
    user_core_frequency: str  # Kullanıcının gerçek frekansı
    surface_persona: str      # Dışarıya yansıttığı
    alignment_score: float      # Uyum skoru (0-1)
    authentic_anchors: list   # Gerçekliğin sabit noktaları
    
    model_config = ConfigDict(extra="forbid")

class MirrorOfTruth:
    """
    Kullanıcının kendine ayna tutması.
    Yüzey vs. Öz ayrımı.
    """
    
    async def execute(self, input_data: Dict, memory, llm_gateway) -> MirrorReflection:
        user_data = input_data.get('user_profile', {})
        sacred_rules = input_data.get('sacred_rules', "")
        
        core_freq = self._extract_core_frequency(user_data)
        anchors = self._find_anchors(user_data)
        
        prompt = (
            f"Sen 'Mirror of Truth' ajanısın. Görevin, verilen kullanıcı verisinden yüzey kimliğini ve gerçek (core) frekansı bulmak.\n"
            f"Kullanıcı Verisi:\n"
            f"Ritüeller: {user_data.get('private_rituals', [])}\n"
            f"Müzik: {user_data.get('late_night_playlist', [])}\n"
            f"Kıskançlık/Arzu: {user_data.get('secret_envies', [])}\n\n"
            f"GERÇEK METRİKLER (NLP ile Çıkarılmış Frekans ve Çapalar):\n"
            f"- Algoritmik Kök Frekans Sinyali: {core_freq}\n"
            f"- NLP Tabanlı Sabit Noktalar (Anchors): {anchors}\n\n"
            f"{sacred_rules}\n"
            f"Şimdi bu ham algoritmik verileri ve profil detaylarını derinlemesine analiz et ve beklenen JSON formatında çıktı üret."
        )
        
        # Pydantic şemasıyla katı sorgu
        return await llm_gateway.query_json(prompt, MirrorReflection)
        
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
