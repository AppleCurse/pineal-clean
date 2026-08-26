"""[022] HumanBehavior model-level evidence contract.

Kurallar:
- Deterministik gözlemler (mikro sinyaller) korunur; yorum katmanı
  (detected_wound / defense_mechanism / achilles_score) ÖLÇÜMSÜZ üretilemez.
- LLM yorumu başarısızsa data_confidence=False + fallback_reason="llm_unavailable",
  achilles_score=0.0, yorum alanları "interpretation_unavailable".
- Hiç gözlem yoksa LLM hiç çağrılmaz; target_evidence_unavailable.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_core.agents.human_behavior import (
    DigitalColdReading,
    HumanBehaviorAnalyzer,
    MicroSignal,
)

INPUT_WITH_TEXT = {
    "target_profile": {
        "bio": "Blogger. Sadece pozitif düşünce.",
        "posts": ["Her şey mükemmel oldu.", "Uzun bir gün...", "Karmaşa oldu."],
        "post_times": [],
        "images": [],
    }
}


class FailingGateway:
    async def query_json(self, *a, **k):
        raise RuntimeError("REAL_LLM_CALL_NOT_EXECUTED: test")


class FakeResultGateway:
    async def query_json(self, *a, **k):
        return DigitalColdReading(
            surface_identity="blogger",
            detected_wound="yüzeysellik",
            defense_mechanism="sessizlik",
            micro_signals=[
                MicroSignal(
                    signal_type="defense", confidence=0.9, location="linguistic",
                    evidence="'Sadece' kelimesi tespiti", psychological_weight=0.8,
                )
            ],
            achilles_score=42.0,
            resonance_potential=0.7,
        )


@pytest.mark.asyncio
async def test_llm_failure_keeps_observations_but_no_interpretation():
    analyzer = HumanBehaviorAnalyzer()
    result = await analyzer.execute(INPUT_WITH_TEXT, None, FailingGateway())

    assert result.data_confidence is False
    assert result.fallback_reason == "llm_unavailable"
    assert result.detected_wound == "interpretation_unavailable"
    assert result.defense_mechanism == "interpretation_unavailable"
    assert result.achilles_score == 0.0
    assert result.resonance_potential == 0.0
    # Gözlemler kaybolmaz (deterministik, ölçümlü)
    assert any(s.signal_type == "defense" for s in result.micro_signals)


@pytest.mark.asyncio
async def test_no_observations_never_calls_llm():
    analyzer = HumanBehaviorAnalyzer()
    gateway = MagicMock()
    gateway.query_json = AsyncMock()

    result = await analyzer.execute(
        {"target_profile": {"bio": "", "posts": [], "post_times": [], "images": []}},
        None,
        gateway,
    )

    gateway.query_json.assert_not_called()
    assert result.data_confidence is False
    assert result.fallback_reason == "target_evidence_unavailable"
    assert result.micro_signals == []
    assert result.achilles_score == 0.0


@pytest.mark.asyncio
async def test_llm_success_is_marked_evidence():
    analyzer = HumanBehaviorAnalyzer()
    result = await analyzer.execute(
        INPUT_WITH_TEXT, None, FakeResultGateway()
    )
    assert result.data_confidence is True
    assert result.fallback_reason is None
    assert result.achilles_score == 42.0
