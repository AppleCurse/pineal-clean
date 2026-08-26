"""Son tarama turu: kalan sahte şablon/default/confidence bulgularının
regresyonları.

Kapsam:
- DarkTriadAnalyzer: markör yoksa exploitability=0.0 (0.5 default yasak);
  strateji kanıt yoksa unavailable / eşik altıysa unobserved.
- ShadowExecutor: kullanıcı vermediyse hedef inanç/eylem default'u YOK;
  strateji yoksa mesaj üretilmez.
- PatternInterrupt: random şablon + placeholder detay yok; prompt yalnızca
  gerçek gözlemi kullanır.
- KeyEngine: rhythm vektör güveni pulse raporunun gerçek durumundan.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_core.agents.pattern_interrupt import PatternInterrupt
from agent_core.domain.pillar_models import EvidenceStatus
from agent_core.engines.key_engine import KeyEngine
from agent_core.psychology.dark_triad import DarkTriadAnalyzer, DarkTriadProfile
from agent_core.shadow.shadow_executor import ShadowExecutor


# ------------------------------------------------------------------ #
# DarkTriad
# ------------------------------------------------------------------ #
def test_dark_triad_no_markers_exploitability_is_zero():
    analyzer = DarkTriadAnalyzer()
    profile = analyzer.analyze({"bio": "Sıradan bir insan.", "posts": []})
    assert profile.exploitability == 0.0
    assert profile.narcissism == 0.0


def test_dark_triad_no_markers_strategy_unavailable():
    analyzer = DarkTriadAnalyzer()
    strategy = analyzer.generate_strategy(DarkTriadProfile())
    assert strategy["vector"] == "unavailable"


def test_dark_triad_below_threshold_strategy_unobserved():
    analyzer = DarkTriadAnalyzer()
    strategy = analyzer.generate_strategy(DarkTriadProfile(narcissism=0.2))
    assert strategy["vector"] == "unobserved"


def test_dark_triad_observed_markers_still_score():
    analyzer = DarkTriadAnalyzer()
    profile = analyzer.analyze({
        "bio": "Mükemmel mükemmel mükemmel mükemmel mükemmel mükemmel mükemmel mükemmel",
        "posts": [],
    })
    assert profile.narcissism > 0.7
    assert profile.exploitability == 0.9
    assert analyzer.generate_strategy(profile)["vector"] == "mirroring"


# ------------------------------------------------------------------ #
# Shadow
# ------------------------------------------------------------------ #
@pytest.mark.asyncio
async def test_shadow_without_observable_strategy_produces_no_message():
    executor = ShadowExecutor()
    result = await executor.execute({
        "target_profile": {"bio": "Sıradan bir insan.", "posts": ["Herkese iyi günler."]},
        "user_profile": {"rituals": ["kahve"], "music": "", "envies": ""},
    })
    assert result.data_confidence is False
    assert result.strategy == "unavailable"
    assert result.message == ""
    assert result.confidence == 0.0
    assert result.fallback_reason in ("dark_triad_markers_unobserved", "strategy_unobserved")


@pytest.mark.asyncio
async def test_shadow_no_fabricated_beliefs_without_input():
    """Kullanıcı hedef inanç vermezse varsayılan inanç enjekte edilmez."""
    executor = ShadowExecutor()
    result = await executor.execute({
        "target_profile": {
            "bio": "Mükemmel mükemmel mükemmel mükemmel mükemmel mükemmel mükemmel mükemmel eşsiz eşsiz olağanüstü benzersiz seçilmiş",
            "posts": ["Başarı tek seçenektir.", "Kontrol bende."],
        },
        "user_profile": {"rituals": ["kahve"], "music": "klasik", "envies": "bağ"},
    })
    # Kullanıcı inancı yok: varsayılan 'anlaşılmak'/'özel hissetmek' yok
    assert "anlaşılmak" not in result.message.lower()
    assert result.data_confidence is True


# ------------------------------------------------------------------ #
# PatternInterrupt: placeholder yasak
# ------------------------------------------------------------------ #
class _PromptCapturingGateway:
    def __init__(self):
        self.prompt = None

    async def query_json(self, prompt, schema, **kwargs):
        self.prompt = prompt
        from agent_core.agents.pattern_interrupt import GeneratedMessage
        return GeneratedMessage(
            message="gözleme dayalı cümle",
            strategy="observation",
            confidence=0.8,
            compliance_score=100.0,
            dialogue_tree=[],
        )


@pytest.mark.asyncio
async def test_pattern_prompt_has_no_fabricated_phrases():
    gateway = _PromptCapturingGateway()
    await PatternInterrupt().execute({
        "target_analysis": {
            "micro_signals": [
                {"signal_type": "defense", "confidence": 0.9, "location": "linguistic",
                 "evidence": "'Sadece' kelimesi tespiti", "psychological_weight": 0.8}
            ]
        },
        "user_mirror": {},
        "sacred_rules": "",
    }, None, gateway)

    assert gateway.prompt is not None
    assert "gözlemlenebilir detay" not in gateway.prompt
    assert "Oyununu görüyorum" not in gateway.prompt
    assert "sıradan insanlara yutturabilirsin" not in gateway.prompt
    assert "BİRİNCİL GÖZLEM (mesajın tek dayanağı): 'Sadece' kelimesi tespiti" in gateway.prompt


@pytest.mark.asyncio
async def test_pattern_dead_helpers_never_fabricate():
    p = PatternInterrupt()
    assert p._extract_specific_detail({}) == "unavailable"
    assert p._extract_micro_signal({}) == "unavailable"


# ------------------------------------------------------------------ #
# KeyEngine rhythm confidence
# ------------------------------------------------------------------ #
class _FakePulse:
    status = EvidenceStatus.WEAK
    rhythm_signature = "2:1"
    baseline_volatility = 0.4


class _FakeObserved:
    status = EvidenceStatus.OBSERVED
    night_energy_share = 0.5
    top_voids = []
    fossils = []
    dominant_attractor = ""
    wells = []
    rhythm_signature = ""
    machine_note = "OBSERVED"


class _FakeInsufficient:
    status = EvidenceStatus.INSUFFICIENT_DATA


def test_key_engine_rhythm_confidence_from_status():
    engine = KeyEngine()

    class _PulseObserved:
        status = EvidenceStatus.OBSERVED
        rhythm_signature = "2:1"
        baseline_volatility = 0.4
        machine_note = "OBSERVED"

    class _PulseWeak:
        status = EvidenceStatus.WEAK
        rhythm_signature = "2:1"
        baseline_volatility = 0.4
        machine_note = "WEAK"

    # OBSERVED → 1.0
    report_observed = engine._sync(
        _FakeObserved(), _FakeObserved(), _FakeObserved(),
        _FakeObserved(), _FakeObserved(), _PulseObserved(),
    )
    rhythm_observed = next(v for v in report_observed.vectors if v.dimension == "rhythm_match")
    assert rhythm_observed.confidence == 1.0

    # WEAK → 0.5 (sabit 0.6 değil)
    report_weak = engine._sync(
        _FakeObserved(), _FakeObserved(), _FakeObserved(),
        _FakeObserved(), _FakeObserved(), _PulseWeak(),
    )
    rhythm_weak = next(v for v in report_weak.vectors if v.dimension == "rhythm_match")
    assert rhythm_weak.confidence == 0.5
