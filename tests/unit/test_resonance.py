import json

import pytest
from agent_core.agents.resonance_calculator import ResonanceCalculator, ResonanceCalculationError

def test_resonance_calculator_normal():
    calc = ResonanceCalculator()
    user_vec = {"depth": 0.8, "energy": 0.5}
    target_vec = {"depth": 0.7, "energy": 0.4}
    
    # Should not raise
    result = calc._cosine_similarity(user_vec, target_vec)
    assert 0.0 < result < 1.0

def test_resonance_calculator_disjoint():
    calc = ResonanceCalculator()
    # No intersecting keys
    user_vec = {"depth": 0.8}
    target_vec = {"energy": 0.4}
    
    result = calc._cosine_similarity(user_vec, target_vec)
    assert result == 0.0  # Valid return for disjoint vectors

def test_resonance_calculator_zero_magnitude():
    calc = ResonanceCalculator()
    user_vec = {"depth": 0.0, "energy": 0.0}
    target_vec = {"depth": 0.7, "energy": 0.4}
    
    with pytest.raises(ResonanceCalculationError) as exc_info:
        calc._cosine_similarity(user_vec, target_vec)
    assert "SIFIR" in str(exc_info.value)

def test_resonance_calculator_malformed():
    calc = ResonanceCalculator()
    user_vec = {}
    target_vec = {"depth": 0.7}
    
    result = calc._cosine_similarity(user_vec, target_vec)
    assert result == 0.0


# ------------------------------------------------------------------ #
# Epistemik onarım sözleşmesi: dramatik etiket yok, gerekçeli örtüşme,
# confirmed | contradicted | inference_gap disiplini, fail-closed.
# ------------------------------------------------------------------ #

DRAMATIC_LABELS = (
    "ATOMIK_REZONANS",
    "YUKSEK_UYUM",
    "ORTA_FREKANS",
    "FREKANS_UYUSMAZLIGI",
)


def _vectors():
    return {
        "user_authentic_vector": {"depth": 0.8, "energy": 0.5},
        "target_authentic_vector": {"depth": 0.7, "energy": 0.4},
    }


def _full_evidence_input():
    data = _vectors()
    data.update({
        "user_profile": {
            "bio": "Derin felsefe, doğa yürüyüşü ve analog fotoğrafçılık ile ilgileniyorum",
            "posts": ["felsefe üzerine uzun düşünceler"],
        },
        "passions": {
            "core_passions": ["felsefe sohbetleri", "fotoğrafçılık"],
            "energizing_topics": ["doğa yürüyüşleri"],
            "data_confidence": True,
        },
        "frictions": {
            "sensitivities": ["yüzeysel sohbet", "pazarlık kabağı"],
            "stress_triggers": ["baskı kurulması"],
            "data_confidence": True,
        },
        "cognitive": {
            "communication_tone": "analitik ve derin",
            "complexity_level": "kavramsal",
            "data_confidence": True,
        },
    })
    return data


async def test_no_dramatic_verdict_labels_anywhere_in_output():
    calc = ResonanceCalculator()
    result = await calc.execute(_full_evidence_input(), memory=None, llm_gateway=None)
    dumped = json.dumps(result.model_dump(), ensure_ascii=False)
    for label in DRAMATIC_LABELS:
        assert label not in dumped, f"sahte kesinlik etiketi çıktıda görünmemeli: {label}"


async def test_state_discipline_is_three_valued():
    calc = ResonanceCalculator()
    for payload in (_full_evidence_input(), _vectors()):
        result = await calc.execute(payload, memory=None, llm_gateway=None)
        assert result.state in ("confirmed", "contradicted", "inference_gap")


async def test_confirmed_state_is_grounded_in_shared_evidence():
    calc = ResonanceCalculator()
    result = await calc.execute(_full_evidence_input(), memory=None, llm_gateway=None)

    assert result.state == "confirmed"
    assert result.data_confidence is True
    # Gerekçe somut paylaşılan kanıtı açıkça göstermeli.
    assert "felsefe" in result.rationale
    assert any("felsefe" in factor for factor in result.decision_factors)
    assert any(d.shared_evidence for d in result.domain_overlaps)
    assert "passions" in result.evidence_sources
    # Vektör kökeni şeffaf beyan edilmeli.
    assert result.vector_provenance["user"]
    assert result.vector_provenance["target"]


async def test_only_llm_vectors_produce_inference_gap_not_a_verdict():
    """Tek başına iki LLM tahmini vektör karar üretemez (fail-closed)."""
    calc = ResonanceCalculator()
    result = await calc.execute(_vectors(), memory=None, llm_gateway=None)

    assert result.state == "inference_gap"
    assert result.data_confidence is False
    # Ölçülen skor raporlanır ama uyum vaadi olarak satılmaz.
    assert result.compatibility_score > 0.0
    assert "model tahmini" in result.rationale
    # Dramatik yaklaşım cümlesi yerine kanıt talebi.
    assert "kanıt" in result.recommended_approach


async def test_user_traits_hitting_target_boundaries_yield_contradicted():
    calc = ResonanceCalculator()
    data = _vectors()
    data.update({
        "user_profile": {"bio": "Yüksek sesli parti ortamlarında bulunmayı seviyorum"},
        "frictions": {
            "sensitivities": ["parti ortamları", "kalabalık gürültü"],
            "data_confidence": True,
        },
        "passions": {
            "core_passions": ["opera", "sergi", "müze"],
            "data_confidence": True,
        },
    })
    result = await calc.execute(data, memory=None, llm_gateway=None)

    assert result.state == "contradicted"
    assert result.data_confidence is True
    frictions_domain = next(d for d in result.domain_overlaps if d.domain == "sürtünme sınırları")
    assert frictions_domain.state == "contradicted"
    assert "parti" in frictions_domain.conflicting_evidence
    assert any("parti" in factor for factor in result.decision_factors)


async def test_data_confidence_false_blob_is_not_counted_as_evidence():
    """Üretici data_confidence=false beyan etmişse içerik eşleşse bile kanıt sayılmaz."""
    calc = ResonanceCalculator()
    data = _vectors()
    data.update({
        "user_profile": {"bio": "Derin felsefe ve fotoğrafçılık seviyorum"},
        "passions": {
            "core_passions": ["felsefe", "fotoğrafçılık", "doğa"],
            "data_confidence": False,  # fallback/канıtsız üretim
            "fallback_reason": "llm_unavailable",
        },
    })
    result = await calc.execute(data, memory=None, llm_gateway=None)

    assert result.state == "inference_gap"
    assert result.data_confidence is False
    assert "passions" not in result.evidence_sources


async def test_output_is_deterministic():
    calc = ResonanceCalculator()
    first = await calc.execute(_full_evidence_input(), memory=None, llm_gateway=None)
    second = await calc.execute(_full_evidence_input(), memory=None, llm_gateway=None)
    assert first.model_dump() == second.model_dump()
