import pytest

from agent_core.agents.pattern_interrupt import GeneratedMessage, PatternInterrupt
from agent_core.schemas.epistemic import EpistemicStatus


class _Gateway:
    """query_json'i LLM'in ham JSON'unu şemaya basarak taklit eder."""

    def __init__(self, payload: dict):
        self.payload = payload

    async def query_json(self, prompt, schema, **kwargs):
        return schema(**self.payload)


def _payload(**overrides):
    base = {
        "message": "O fotoğraftaki atölye detayı dikkatimi çekti.",
        "strategy": "observational",
        "confidence": 0.7,
        "compliance_score": 95.0,
        "dialogue_tree": [],
        "data_confidence": True,
        "fallback_reason": None,
    }
    base.update(overrides)
    return base


def _analysis():
    return {
        "micro_signals": [
            {"evidence": "atölye tezgâhı görünüyor", "psychological_weight": 0.9}
        ],
    }


@pytest.mark.asyncio
async def test_pattern_interrupt_returns_unavailable_without_grounded_evidence():
    result = await PatternInterrupt().execute({"target_analysis": {}}, None, None)
    assert result.strategy == "UNAVAILABLE"
    assert result.confidence == 0.0
    assert result.data_confidence is False
    assert result.fallback_reason == "insufficient_grounded_evidence"
    assert result.epistemic == EpistemicStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_grounded_message_is_code_stamped_interpreted_with_evidence():
    """B-2: dolu mesaj + grounded kanıt -> bayrak AÇIK ama damga INTERPRETED;
    evidence_refs yalnızca gerçek kanıt kümesini taşır."""
    gw = _Gateway(_payload())
    result = await PatternInterrupt().execute({"target_analysis": _analysis()}, None, gw)
    assert result.data_confidence is True
    assert result.fallback_reason is None
    assert result.epistemic == EpistemicStatus.INTERPRETED
    assert result.evidence_refs == ["atölye tezgâhı görünüyor"]
    assert result.message  # içerik korunur


@pytest.mark.asyncio
async def test_model_cannot_self_open_flag_with_empty_message():
    """B-2: model data_confidence=true dese bile mesaj boşsa bayrak KAPALI kalır
    ve boş mesaj dışarı sızmadan UNAVAILABLE damgası basılır."""
    gw = _Gateway(_payload(message="   ", data_confidence=True))
    result = await PatternInterrupt().execute({"target_analysis": _analysis()}, None, gw)
    assert result.data_confidence is False
    assert result.message == ""
    assert result.fallback_reason  # "llm_returned_ungrounded_message" veya model nedeni
    assert result.epistemic == EpistemicStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_model_self_veto_closes_flag_and_suppresses_message():
    """B-2: prompt 'kanıt yetersizse data_confidence=false döndür' der; modelin
    bu vetosu artık ezilmiyor (eski kod koşulsuz True basıyordu)."""
    gw = _Gateway(_payload(data_confidence=False, fallback_reason="insufficient_grounded_evidence"))
    result = await PatternInterrupt().execute({"target_analysis": _analysis()}, None, gw)
    assert result.data_confidence is False
    assert result.message == ""  # veto edilmiş içerik sızmasın
    assert result.epistemic == EpistemicStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_model_cant_self_stamp_verified():
    """Sözleşme kuralı 1: LLM JSON'da epistemic='verified' gönderse bile
    kod INTERPRETED'a zorlar — model kendi damgasını basamaz."""
    gw = _Gateway(_payload(epistemic="verified", evidence_refs=["uydurma-ref"]))
    result = await PatternInterrupt().execute({"target_analysis": _analysis()}, None, gw)
    assert result.epistemic == EpistemicStatus.INTERPRETED
    assert result.evidence_refs == ["atölye tezgâhı görünüyor"]
