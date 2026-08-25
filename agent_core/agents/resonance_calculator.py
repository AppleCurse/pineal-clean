import numpy as np
from pydantic import BaseModel, ConfigDict
from typing import Dict

class ResonanceCalculationError(Exception):
    """Fırlatılır: Rezonans hesaplaması matematiksel olarak imkansızsa (örn: boş vektörler)."""
    pass

class ResonanceProfile(BaseModel):
    compatibility_score: float
    frequency_match: Dict[str, float]
    recommended_approach: str
    red_flags: list

    model_config = ConfigDict(extra="forbid")

class ResonanceCalculator:
    """İki profil vektörü arasındaki rezonansı hesaplar."""

    async def execute(self, input_data: Dict, memory, llm_gateway) -> ResonanceProfile:
        # Resonance is a decision based on two observed/calculated vectors.  Never
        # substitute a pleasant-looking default when one side is unavailable.
        user_vector = input_data.get('user_authentic_vector')
        if not self._has_required_dimensions(user_vector):
            raise ResonanceCalculationError(
                "Kullanıcı authentic vector'u mevcut değil; rezonans hesaplanamaz."
            )

        target_vector = input_data.get('target_authentic_vector')
        if target_vector is not None and not self._has_required_dimensions(target_vector):
            raise ResonanceCalculationError(
                "Hedef authentic vector'u geçersiz; rezonans hesaplanamaz."
            )
        if not target_vector:
            raise ResonanceCalculationError(
                "Hedef authentic vector'u mevcut değil; metin, achilles skoru veya varsayılan değerlerden rezonans türetilemez."
            )

        similarity = self._cosine_similarity(user_vector, target_vector)

        if similarity > 0.85:
            approach = "ATOMIK_REZONANS - Derin bağlantı mümkün"
        elif similarity > 0.70:
            approach = "YUKSEK_UYUM - Güçlü çekim alanı"
        elif similarity > 0.50:
            approach = "ORTA_FREKANS - Dikkatli yaklaşım"
        else:
            approach = "FREKANS_UYUSMAZLIGI - Sistem kapat, yeni hedef"

        return ResonanceProfile(
            compatibility_score=similarity,
            frequency_match=self._detailed_match(user_vector, target_vector),
            recommended_approach=approach,
            red_flags=self._detect_red_flags(user_vector, target_vector),
        )

    @staticmethod
    def _has_required_dimensions(vector: object) -> bool:
        if not isinstance(vector, dict):
            return False
        return all(
            isinstance(vector.get(dimension), (int, float))
            for dimension in ("depth", "energy")
        )

    def _detailed_match(self, vec1: Dict, vec2: Dict) -> Dict[str, float]:
        return {'overall_match': self._cosine_similarity(vec1, vec2)}

    def _cosine_similarity(self, vec1: Dict, vec2: Dict) -> float:
        numeric_keys = {
            k for k in set(vec1.keys()) & set(vec2.keys())
            if isinstance(vec1[k], (int, float)) and isinstance(vec2.get(k), (int, float))
        }
        if not numeric_keys:
            return 0.0

        dot_product = sum(float(vec1[k]) * float(vec2[k]) for k in numeric_keys)
        magnitude1 = np.sqrt(sum(float(vec1[k])**2 for k in numeric_keys))
        magnitude2 = np.sqrt(sum(float(vec2[k])**2 for k in numeric_keys))

        if magnitude1 == 0 or magnitude2 == 0:
            import logging
            logging.warning("Resonance calculation failed: Zero magnitude vector encountered.")
            raise ResonanceCalculationError("Vektörlerden birinin magnitude'u SIFIR. Hesaplama yapılamaz.")

        return float(dot_product / (magnitude1 * magnitude2))

    def _detect_red_flags(self, user: Dict, target: Dict) -> list:
        flags = []
        if user.get('depth', 0) > 0.8 and target.get('surface_focus', 0) > 0.8:
            flags.append("DERINLIK_UYUSMAZLIĞI")
        if user.get('energy', 0.5) < 0.3 and target.get('energy', 0.5) > 0.8:
            flags.append("ENERJI_UYUSMAZLIĞI")
        return flags
