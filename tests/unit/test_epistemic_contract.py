"""Epistemik sınav — roadmap Faz 1'in çevirme testi.

Soru: "Bir LLM yorumu pipeline'ın hiçbir noktasında etiketsiz kanıta dönüşemiyor mu?"
Bu dosyadaki her test o cümlenin bir cebini mühürler.
"""
from __future__ import annotations

import pytest

from agent_core.agents.resonance_calculator import (
    ResonanceCalculationError,
    ResonanceCalculator,
)
from agent_core.schemas.epistemic import (
    EpistemicResult,
    EpistemicStatus,
    is_estimate,
    status_weight,
)
from agent_core.services.canonical_memory import CanonicalMemory


# --- Sözleşme çekirdeği ------------------------------------------------------- #

def test_default_status_is_never_observed_nor_verified():
    """Statüyü kod yazar: model kendini ölçülmüş/teyitli ilan edemez."""
    m = EpistemicResult()
    assert m.epistemic is EpistemicStatus.INTERPRETED
    assert m.epistemic not in (EpistemicStatus.OBSERVED, EpistemicStatus.VERIFIED)
    assert m.evidence_refs == []


def test_marker_readers():
    assert is_estimate({"_epistemic": "model_estimate"}) is True
    assert is_estimate({"epistemic": "model_estimate"}) is True
    assert is_estimate({"_epistemic": "measured"}) is False
    assert is_estimate({}) is False
    # etiketsiz ≠ temiz; ağırlık yalnız statüye göre
    assert status_weight({}) == 1.0
    assert status_weight({"_epistemic": "unavailable"}) == 0.0
    assert status_weight({"epistemic": "hypothesis"}) == pytest.approx(0.35)
    assert status_weight({"epistemic": "verified"}) == 1.0


# --- Tüketici kapısı: rezonans ------------------------------------------------ #

@pytest.mark.asyncio
async def test_model_estimate_vector_cannot_become_numeric_evidence():
    """LLM psikolojik çıkarımı etiketsiz skora dönüşemez (B-1/A-2)."""
    calc = ResonanceCalculator()
    with pytest.raises(ResonanceCalculationError, match="model_estimate"):
        await calc.execute(
            {
                "user_authentic_vector": {"depth": 0.8, "energy": 0.4, "_epistemic": "model_estimate"},
                "target_authentic_vector": {"depth": 0.7, "energy": 0.5},
            },
            memory=None, llm_gateway=None,
        )


@pytest.mark.asyncio
async def test_model_estimate_on_target_side_also_blocked():
    calc = ResonanceCalculator()
    with pytest.raises(ResonanceCalculationError, match="model_estimate"):
        await calc.execute(
            {
                "user_authentic_vector": {"depth": 0.8, "energy": 0.4},
                "target_authentic_vector": {"depth": 0.7, "energy": 0.5, "_epistemic": "model_estimate"},
            },
            memory=None, llm_gateway=None,
        )


@pytest.mark.asyncio
async def test_explicit_concession_allows_but_stamps_output():
    """Açık taviz varsa skor üretilir ama asla 'ölçüm' gibi taşınmaz."""
    calc = ResonanceCalculator(allow_estimated=True)
    profile = await calc.execute(
        {
            "user_authentic_vector": {"depth": 0.8, "energy": 0.4, "_epistemic": "model_estimate"},
            "target_authentic_vector": {"depth": 0.7, "energy": 0.5},
        },
        memory=None, llm_gateway=None,
    )
    assert 0.0 < profile.compatibility_score <= 1.0
    assert profile.epistemic == "model_estimate"


@pytest.mark.asyncio
async def test_legacy_unstamped_vectors_still_compute():
    """Geriye uyumluluk: damgasız vektör hesaplanır ama 'unstamped' damgası taşır."""
    calc = ResonanceCalculator()
    profile = await calc.execute(
        {
            "user_authentic_vector": {"depth": 0.8, "energy": 0.4},
            "target_authentic_vector": {"depth": 0.7, "energy": 0.5},
        },
        memory=None, llm_gateway=None,
    )
    assert profile.epistemic == "unstamped"


@pytest.mark.asyncio
async def test_measured_vectors_carry_measured_stamp():
    calc = ResonanceCalculator()
    profile = await calc.execute(
        {
            "user_authentic_vector": {"depth": 0.8, "energy": 0.4, "_epistemic": "measured"},
            "target_authentic_vector": {"depth": 0.7, "energy": 0.5, "_epistemic": "measured"},
        },
        memory=None, llm_gateway=None,
    )
    assert profile.epistemic == "measured"  # iki taraf da ölçüm damgalı -> skor ölçülebilir diye damgalanır


# --- Tüketici kapısı: bellek agregasyonu -------------------------------------- #

def _ev(conf, marker=None):
    result = {"confidence": conf}
    if marker:
        result["epistemic"] = marker
    return {"evidence_type": "agent_output", "result": result}


def test_memory_weighting_prefers_verified_over_hypothesis():
    mem = CanonicalMemory(memory_dir=None) if False else CanonicalMemory.__new__(CanonicalMemory)
    legacy = mem._calculate_overall_confidence([_ev(1.0), _ev(0.2)])
    assert legacy == 0.6  # eski düz ortalama korunur (damgasız → legacy)

    weighted = mem._calculate_overall_confidence([_ev(1.0, "verified"), _ev(0.2, "hypothesis")])
    # (1.0*1.0 + 0.2*0.35) / 1.35 ≈ 0.793 — hipotez, teyitlinin yanında güveni şişiremez
    assert weighted == pytest.approx(0.793, abs=1e-3)
    assert weighted > legacy


def test_memory_unavailable_contributes_nothing():
    mem = CanonicalMemory.__new__(CanonicalMemory)
    only_unavailable = mem._calculate_overall_confidence([_ev(0.9, "unavailable")])
    assert only_unavailable == 0.0  # UNAVAILABLE güven toplamına giremez
    mixed = mem._calculate_overall_confidence([_ev(0.9, "unavailable"), _ev(0.5, "verified")])
    assert mixed == 0.5
