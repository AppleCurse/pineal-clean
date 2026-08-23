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
            data_fields = [v for k, v in result_dict.items() if k != "confidence"]
            total_fields = len(result_dict)
            if total_fields > 0:
                empty_fields = sum(
                    1 for v in result_dict.values()
                    if v is None or v == [] or v == {} or (isinstance(v, str) and (v == '' or 'bulunamadı' in v.lower()))
                )
                data_score = 1.0 - (empty_fields / total_fields)
                if data_fields and all(v is None or v == [] or v == {} or (isinstance(v, str) and (v == '' or 'bulunamadı' in v.lower())) for v in data_fields):
                    is_empty = True
                    confidence = 0.1
                else:
                    if confidence is None:
                        confidence = data_score
                    else:
                        if data_score >= 0.6:
                            confidence = min(confidence, data_score)
                        elif data_score >= 0.34 and confidence >= 0.7:
                            # Bilincli bulunamadi (model emin + makul doluluk): taban gecerli
                            confidence = 0.65
                        else:
                            # Zayif veri / kararsiz model: koruma devrede
                            confidence = min(confidence, data_score)
        elif 'evidence' in result_text and 'bulunamadı' in result_text:
            is_empty = True
            confidence = 0.1

        if is_empty:
            return UncertaintyReport(is_suspicious=True, confidence=confidence or 0.1, reason="Eksik kanıt (Tüm alanlar boş veya veri yetersiz). Router kesilmeli.")
        if confidence is not None and confidence > 0.95 and has_absolutes:
            return UncertaintyReport(is_suspicious=True, confidence=0.9, reason="Aşırı kesinlik + yüksek confidence = Halüsinasyon şüphesi")
        return UncertaintyReport(is_suspicious=False, confidence=confidence if confidence is not None else 1.0, reason="Güvenli")
