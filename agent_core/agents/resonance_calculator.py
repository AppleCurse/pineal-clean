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
        user_vector = input_data.get('user_authentic_vector', {'depth': 0.9, 'energy': 0.3})

        target_vector = input_data.get('target_authentic_vector')
        if not target_vector:
            target_obj = input_data.get('target_analysis', {})
            if hasattr(target_obj, 'model_dump'):
                t_dict = target_obj.model_dump()
            else:
                t_dict = target_obj if isinstance(target_obj, dict) else {}

            if 'depth' in t_dict and 'energy' in t_dict:
                target_vector = {
                    'depth': float(t_dict['depth']),
                    'energy': float(t_dict['energy']),
                }
            else:
                # Hedef metinlerinden gerçek enerji ve derinlik çıkarımı
                target_text = t_dict.get('bio', '') + " " + " ".join(t_dict.get('posts', []))
                if not target_text.strip():
                    if 'achilles_score' in t_dict:
                        achilles = float(t_dict.get('achilles_score', 50))
                        depth_val = achilles / 100.0
                        energy_val = 1.0 - depth_val
                    else:
                        target_text = str(t_dict)
                        import re
                        words = re.findall(r'\b\w+\b', target_text.lower())
                        unique_words = set(words)
                        ttr = len(unique_words) / len(words) if words else 0.5
                        sentences = [s for s in re.split(r'[.!?]+', target_text) if s.strip()]
                        avg_sentence_len = len(words) / max(1, len(sentences))
                        depth_val = (ttr * 0.6) + (min(avg_sentence_len, 20) / 20 * 0.4)
                        exclamations = target_text.count('!')
                        caps = sum(1 for c in target_text if c.isupper())
                        total_chars = max(1, len(target_text))
                        energy_val = (exclamations * 0.1) + ((caps / total_chars) * 2.0)
                else:
                    import re
                    words = re.findall(r'\b\w+\b', target_text.lower())
                    unique_words = set(words)
                    ttr = len(unique_words) / len(words) if words else 0.5
                    sentences = [s for s in re.split(r'[.!?]+', target_text) if s.strip()]
                    avg_sentence_len = len(words) / max(1, len(sentences))
                    depth_val = (ttr * 0.6) + (min(avg_sentence_len, 20) / 20 * 0.4)
                    exclamations = target_text.count('!')
                    caps = sum(1 for c in target_text if c.isupper())
                    total_chars = max(1, len(target_text))
                    energy_val = (exclamations * 0.1) + ((caps / total_chars) * 2.0)
                
                target_vector = {
                    'depth': float(np.clip(depth_val, 0.1, 1.0)),
                    'energy': float(np.clip(energy_val, 0.1, 1.0)),
                }

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
