from pydantic import BaseModel, ConfigDict
from typing import Any

class UncertaintyReport(BaseModel):
    is_suspicious: bool
    confidence: float
    reason: str
    model_config = ConfigDict(extra="forbid")

class UncertaintyEngine:
    HALUCINATION_MARKERS = [
        'kesinlikle', 'mutlaka', 'her zaman', 'asla',
        'kesin olarak', 'şüphesiz'
    ]

    def evaluate(self, result: Any, agent_name: str) -> UncertaintyReport:
        result_text = str(result)
        has_absolutes = any(marker in result_text.lower() for marker in self.HALUCINATION_MARKERS)
        confidence = getattr(result, 'confidence', None)
        is_empty = False

        if isinstance(result, BaseModel):
            result_dict = result.model_dump()
            total_fields = len(result_dict)
            if total_fields > 0:
                empty_fields = sum(1 for v in result_dict.values() if not v or (isinstance(v, str) and 'bulunamadı' in v.lower()))
                data_score = 1.0 - (empty_fields / total_fields)
                if confidence is None:
                    confidence = data_score
                else:
                    confidence = min(confidence, data_score)

                if empty_fields == total_fields:
                    is_empty = True
                    confidence = 0.1

        if 'evidence' in result_text and 'bulunamadı' in result_text:
            is_empty = True
            confidence = 0.1

        if is_empty:
            return UncertaintyReport(is_suspicious=True, confidence=confidence, reason="Eksik kanıt (Boş liste veya 'bulunamadı'). Router kesilmeli.")
        if confidence > 0.95 and has_absolutes:
            return UncertaintyReport(is_suspicious=True, confidence=0.9, reason="Aşırı kesinlik + yüksek confidence = Halüsinasyon şüphesi")
        return UncertaintyReport(is_suspicious=False, confidence=confidence, reason="Güvenli")
