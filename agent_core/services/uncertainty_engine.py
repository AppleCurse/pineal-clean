import json
import logging
from typing import Any, Dict, Tuple
from pydantic import BaseModel, ConfigDict

try:
    from agent_core.config_loader import DecisionConfig
except Exception:
    from config_loader import DecisionConfig


class UncertaintyReport(BaseModel):
    is_suspicious: bool
    confidence: float
    reason: str
    data_score: float = 0.0
    breakdown: Dict[str, Any] = {}
    model_config = ConfigDict(extra="forbid")

class UncertaintyEngine:
    HALUCINATION_MARKERS = [
        'kesinlikle', 'mutlaka', 'her zaman', 'asla',
        'kesin olarak', 'şüphesiz'
    ]

    def __init__(self):
        self.config = DecisionConfig.load()
        self.logger = logging.getLogger(__name__)

    def calculate_data_score(
        self, 
        output_dict: Dict[str, Any], 
        agent_name: str
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate data quality score with detailed breakdown based on config.
        """
        agent_config = self.config.get_agent_config(agent_name)
        field_weights = agent_config.field_weights
        empty_list_penalty = agent_config.empty_list_penalty
        semantic_richness_weight = agent_config.semantic_richness_weight
        
        breakdown = {}
        total_score = 0.0
        total_weight = 0.0
        
        # If no specific field weights are defined, just use a simple ratio
        if not field_weights:
            data_fields = [v for k, v in output_dict.items() if k != "confidence" and k != "data_confidence" and k != "fallback_reason"]
            total_fields = len(data_fields)
            if total_fields == 0:
                return 0.0, {"reason": "No data fields"}
                
            empty_fields = sum(
                1 for v in data_fields
                if v is None or v == [] or v == {} or (isinstance(v, str) and (v == '' or 'bulunamadı' in v.lower()))
            )
            data_score = 1.0 - (empty_fields / total_fields)
            return data_score, {"simple_ratio": data_score}

        for field, weight in field_weights.items():
            if field not in output_dict:
                breakdown[field] = {"present": False, "score": 0.0, "weight": weight}
                total_weight += weight
                continue
            
            value = output_dict[field]
            field_score = self._score_field_value(value, empty_list_penalty, semantic_richness_weight)
            
            breakdown[field] = {
                "present": True,
                "score": field_score,
                "weight": weight,
                "weighted_score": field_score * weight
            }
            
            total_score += field_score * weight
            total_weight += weight
        
        final_score = total_score / total_weight if total_weight > 0 else 0.0
        
        self.logger.info(
            f"Data score for {agent_name}: {final_score:.2f}\n"
            f"Breakdown: {json.dumps(breakdown, indent=2)}"
        )
        
        return final_score, breakdown

    def _score_field_value(self, value: Any, empty_list_penalty: float, semantic_richness_weight: float) -> float:
        """Score individual field value (0.0 to 1.0)."""
        if value is None:
            return 0.0
        
        if isinstance(value, list):
            if len(value) == 0:
                # Boş liste cezası (eskisi gibi direkt 0.0 vermek yerine penalty uygulanabilir, 
                # ama genelde boş liste 0.0 veya penalty kadar olmalı)
                return empty_list_penalty
            # Eleman sayısına göre ve semantic richness'a göre
            # Örneğin 3 elemanlı bir liste iyidir.
            length_score = min(len(value) / 3.0, 1.0)
            # Elemanların uzunluğu (semantic richness)
            str_lengths = [len(str(item)) for item in value]
            avg_length = sum(str_lengths) / len(str_lengths) if str_lengths else 0
            semantic_score = min(avg_length / 50.0, 1.0)
            
            return (length_score * (1.0 - semantic_richness_weight)) + (semantic_score * semantic_richness_weight)
            
        if isinstance(value, dict):
            if len(value) == 0:
                return empty_list_penalty
            return 0.8
        
        if isinstance(value, str):
            if not value.strip() or 'bulunamadı' in value.lower():
                return 0.0
            # Longer strings = richer data
            return min(len(value) / 100.0, 1.0)
        
        if isinstance(value, (int, float, bool)):
            return 0.8  # Primitives are moderate confidence
        
        return 0.5  # Default for other types

    def evaluate(self, result: Any, agent_name: str) -> UncertaintyReport:
        result_text = str(result)
        has_absolutes = any(marker in result_text.lower() for marker in self.HALUCINATION_MARKERS)
        llm_confidence = getattr(result, 'confidence', None)
        data_conf_flag = getattr(result, 'data_confidence', True)
        
        agent_config = self.config.get_agent_config(agent_name)
        
        data_score = 0.0
        breakdown = {}
        is_empty = False

        if isinstance(result, BaseModel):
            result_dict = result.model_dump()
            data_score, breakdown = self.calculate_data_score(result_dict, agent_name)
            
            # Eski is_empty mantığını da kısmen koruyalım
            data_fields = [v for k, v in result_dict.items() if k not in ("confidence", "data_confidence", "fallback_reason")]
            if data_fields and all(v is None or v == [] or v == {} or (isinstance(v, str) and (v == '' or 'bulunamadı' in v.lower())) for v in data_fields):
                is_empty = True
        elif 'evidence' in result_text and 'bulunamadı' in result_text:
            is_empty = True

        # Calculate combined confidence
        if llm_confidence is None:
            combined_confidence = data_score
        else:
            # Weighted approach or taking the minimum if data score is too low
            if data_score >= agent_config.min_data_score:
                # LLM confidence is acceptable
                combined_confidence = min(llm_confidence, data_score)
            else:
                combined_confidence = data_score

        # Check conditions
        if not data_conf_flag:
            # Fallback data
            return UncertaintyReport(
                is_suspicious=False, 
                confidence=combined_confidence, 
                reason="Fallback modu devrede.",
                data_score=data_score,
                breakdown=breakdown
            )

        if is_empty:
            return UncertaintyReport(
                is_suspicious=True, 
                confidence=0.1, 
                reason="Eksik kanıt (Tüm alanlar boş veya veri yetersiz).",
                data_score=data_score,
                breakdown=breakdown
            )

        if combined_confidence > 0.95 and has_absolutes:
            return UncertaintyReport(
                is_suspicious=True, 
                confidence=0.9, 
                reason="Aşırı kesinlik + yüksek confidence = Halüsinasyon şüphesi",
                data_score=data_score,
                breakdown=breakdown
            )

        if combined_confidence < agent_config.min_llm_confidence:
            return UncertaintyReport(
                is_suspicious=True,
                confidence=combined_confidence,
                reason=f"Düşük güven ({combined_confidence:.2f} < {agent_config.min_llm_confidence}).",
                data_score=data_score,
                breakdown=breakdown
            )

        return UncertaintyReport(
            is_suspicious=False, 
            confidence=combined_confidence, 
            reason="Güvenli",
            data_score=data_score,
            breakdown=breakdown
        )
