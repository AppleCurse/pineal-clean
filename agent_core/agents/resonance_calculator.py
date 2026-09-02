import os

import numpy as np
from pydantic import BaseModel, ConfigDict
from typing import Dict, Optional

from agent_core.schemas.epistemic import is_estimate

class ResonanceCalculationError(Exception):
    """Fırlatılır: Rezonans hesaplaması matematiksel olarak imkansızsa (örn: boş vektörler)."""
    pass

class ResonanceProfile(BaseModel):
    compatibility_score: float
    frequency_match: Dict[str, float]
    recommended_approach: str
    red_flags: list
    # Epistemik damga: skorun girdisi ölçülmüş mü, LLM tahmini mi, etiketsiz mi?
    # Tüketici (UI/karar) bu damgayı görmeden skoru 'ölçüm' gibi gösteremez.
    epistemic: str = "unstamped"

    model_config = ConfigDict(extra="forbid")

class ResonanceCalculator:
    """İki profil vektörü arasındaki rezonansı hesaplar.

    Epistemik kapı (roadmap A-2/B-1): `_epistemic: model_estimate` damgalı
    vektör (LLM'in ürettiği psikolojik çıkarım) varsayılan olarak skora GİREMEZ.
    Açık taviz ancak `allow_estimated=True` ile verilir ve çıktı o zaman
    `epistemic="model_estimate"` olarak damgalanır — sayı 'ölçüm' gibi taşınmaz.
    """

    def __init__(self, allow_estimated: Optional[bool] = None) -> None:
        if allow_estimated is None:
            allow_estimated = os.getenv("PINEAL_ALLOW_ESTIMATED_RESONANCE", "false").lower() == "true"
        self.allow_estimated = allow_estimated

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

        estimate_seen = self._check_epistemic(user_vector, "kullanıcı") or self._check_epistemic(target_vector, "hedef")
        both_measured = self._is_measured(user_vector) and self._is_measured(target_vector)

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
            epistemic="model_estimate" if estimate_seen else ("measured" if both_measured else "unstamped"),
        )

    @staticmethod
    def _is_measured(vector: object) -> bool:
        from agent_core.schemas.epistemic import MEASURED_MARKERS, read_marker
        return read_marker(vector) in MEASURED_MARKERS

    def _check_epistemic(self, vector: Dict, side: str) -> bool:
        """Damgalı tahmin girişse kapıyı çal; True dönerse çıktı 'model_estimate' damgalanır."""
        if not is_estimate(vector):
            return False
        if not self.allow_estimated:
            raise ResonanceCalculationError(
                f"{side.capitalize()} authentic vector'u 'model_estimate' damgalı; LLM tahmini "
                "numeric kanıt gibi skora giremez. Açık taviz: PINEAL_ALLOW_ESTIMATED_RESONANCE=true "
                "(çıktı o zaman da model_estimate olarak damgalanır)."
            )
        return True

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
        """[033] fix: eski 'surface_focus' koşulu hiçbir üretici tarafından
        doldurulmadığı için DERINLIK_UYUSMAZLIGI bayrağı üretilemezdi (ölü dal).
        Gerçek vektör boyutlarından türetilir."""
        flags = []

        def _num(vec: Dict, key: str):
            v = vec.get(key)
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        u_depth, t_depth = _num(user, "depth"), _num(target, "depth")
        if u_depth is not None and t_depth is not None and abs(u_depth - t_depth) > 0.35:
            flags.append("DERINLIK_UYUSMAZLIĞI")

        u_energy, t_energy = _num(user, "energy"), _num(target, "energy")
        if u_energy is not None and t_energy is not None and u_energy < 0.3 and t_energy > 0.8:
            flags.append("ENERJI_UYUSMAZLIĞI")

        return flags
