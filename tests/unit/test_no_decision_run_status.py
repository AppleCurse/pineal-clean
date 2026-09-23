"""GÖREV TAMAMLANDI ≠ KARAR ÜRETİLDİ — `completed_no_decision` sözleşmesi.

[RÖNTGEN 2026-09-23] Ölçülen eski kusur: `UncertaintyEngine.evaluate`,
`resonance_calc` çıktısı kendi sözleşmesiyle "karar değil"
(`data_confidence=False`, `resonance_calculator.py:111`) dediğinde
`confidence = max(0.75, compatibility_score)` üretiyordu. Yani:

  * ölçülmeyen bir güven UYDURULUYORDU (0.0 benzerlik → 0.75),
  * bu taban executor'ın `LOW_CONFIDENCE` kapısını atlatıyordu,
  * gerekçe metni "Rezonans analizi tamamlandı" diyerek çıktıyı
    doğrulanmış bir karar gibi gösteriyordu.

Tabanı kaldırmanın naif yolu (güven 0.0 → koşu `halted`) bu kez
`state=inference_gap` bilgisini rapordan siliyordu, çünkü halted koşunun
çıktısı `status`'a işlenmiyor. Doğru ayrım yeni bir koşu durumu:

    completed_no_decision  = ajan KOŞTU, çıktı KAYDEDİLDİ, ama KARAR DEĞİL.

Bu dosya o ayrımı uçtan uca kilitler: uncertainty raporu → executor koşu
kaydı → DecisionEngine hükmü → genel fail-closed yolun GEVŞEMEMESİ.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from agent_core.agents.resonance_calculator import EvidenceOverlap, ResonanceProfile
from agent_core.domain.memory_models import AgentRun
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.services.decision_engine import DecisionEngine
from agent_core.services.uncertainty_engine import UncertaintyEngine, UncertaintyReport
from agent_core.config_loader import DecisionConfig
from agent_core.task_executor import PinealExecutor


def _inference_gap_profile(score: float = 0.0) -> ResonanceProfile:
    """Rezonans motorunun GERÇEK 'karar değil' çıktısı (vektörler yok)."""
    return ResonanceProfile(
        state="inference_gap",
        compatibility_score=score,
        data_confidence=False,
        rationale="authentic vektörler sağlanamadı; ölçüm yok",
        decision_factors=["vector_unavailable"],
        recommended_approach="Karar üretilemez; önce kanıt gerekir.",
        evidence_sources=[],
        vector_provenance={"user": "unavailable", "target": "unavailable"},
    )


# --------------------------------------------------------------------------- #
# 1) UncertaintyEngine: taban yok, no_decision=True
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("score", [0.0, 0.42, 0.91])
def test_resonance_no_decision_reports_measured_confidence_without_floor(score):
    report = UncertaintyEngine().evaluate(_inference_gap_profile(score), "resonance_calc")

    assert isinstance(report, UncertaintyReport)
    assert report.no_decision is True
    assert report.is_suspicious is False, "rezonans görev akışını durdurmaz"
    # UYDURMA TABAN YOK: güven = ölçülen benzerlik.
    assert report.confidence == score
    assert "KARAR DEĞİL" in report.reason
    assert "data_confidence=False" in report.reason
    assert "tamamlandı" not in report.reason, "eski sahte 'analiz tamamlandı' iddiası dönemez"


def test_no_decision_defaults_false_for_every_other_report():
    """`no_decision` opt-in'dir: varsayılan False, yani fail-closed yol aynı."""
    assert UncertaintyReport(is_suspicious=False, confidence=0.9, reason="x").no_decision is False


def test_llm_agent_with_data_confidence_false_still_fails_closed():
    """Genel kural GEVŞEMEDİ: LLM ajanı data_confidence=False derse şüphelidir."""
    result = SimpleNamespace(
        confidence=0.9,
        data_confidence=False,
        fallback_reason="provider_error",
        core_passions=["x"],
    )
    report = UncertaintyEngine().evaluate(result, "passion_mapper")

    assert report.no_decision is False
    assert report.is_suspicious is True
    assert report.confidence == 0.0
    assert report.reason != "Güvenli"


# --------------------------------------------------------------------------- #
# 2) Executor: koşu kaydı completed_no_decision, çıktı KORUNUR
# --------------------------------------------------------------------------- #
class _DummyResult(BaseModel):
    compatibility_score: float = 0.9


def _executor(routed: list[str], resonance_result) -> PinealExecutor:
    executor = PinealExecutor()
    executor._agent_tracker = None

    route = MagicMock()
    route.agents = list(routed)
    router = MagicMock()
    router.analyze = AsyncMock(return_value=route)
    executor.router = router

    executor.memory = MagicMock()
    executor.memory.merge_evidence = AsyncMock()
    executor.injector = MagicMock()
    executor.injector.fetch_active_rules.return_value = {}
    executor.llm_gateway = MagicMock()
    executor.llm_gateway.query = AsyncMock(return_value="kanıt")

    for name in executor.agents:
        agent = MagicMock()
        agent.execute = AsyncMock(return_value=_DummyResult())
        executor.agents[name] = agent
    executor.agents["resonance_calc"].execute = AsyncMock(return_value=resonance_result)
    executor._download_images = AsyncMock(return_value=[])
    return executor


@pytest.mark.asyncio
async def test_resonance_inference_gap_run_is_recorded_as_no_decision():
    executor = _executor(["resonance_calc"], _inference_gap_profile(0.0))

    status = await executor.execute_task({"target_profile": {}}, "task-no-decision")

    run = status.agent_runs["resonance_calc"]
    assert run.status == "completed_no_decision"
    assert run.decision_grade is False
    # Çıktı KAYBOLMAZ: inference_gap bilgisi raporda kalır (naif "halt" çözümü
    # bunu siliyordu).
    assert run.output_summary["state"] == "inference_gap"
    assert run.output_summary["data_confidence"] is False
    # Güven uydurulmaz: ölçülen 0.0 yazılır (eski hâlde 0.75 olurdu).
    assert run.confidence == 0.0
    # Ajan gerçekten koştu: halted değil, görev de kritik durmadı.
    assert run.error_code is None
    assert status.status != "halted_critical"
    assert "resonance_calc" in status.completed_agents


@pytest.mark.asyncio
async def test_measured_resonance_run_stays_decision_grade():
    """Vektörler ÖLÇÜLDÜYSE (data_confidence=True) 'completed' yolu aynen durur.

    Yani `no_decision` bir kaçış kapağı değil: yalnızca ajanın kendi
    sözleşmesinin "karar değil" dediği durumda devreye girer.
    """
    profile = ResonanceProfile(
        state="confirmed",
        compatibility_score=0.82,
        data_confidence=True,
        rationale="İki vektör de ölçüldü; frekans örtüşmesi somut kanıta dayanıyor.",
        decision_factors=["frequency_match", "domain_overlap"],
        domain_overlaps=[
            EvidenceOverlap(
                domain="tutkular", state="confirmed", overlap=0.8,
                shared_evidence=["satranç", "mühendislik"],
                rationale="iki profilde de ölçüldü",
            )
        ],
        frequency_match={"analitik": 0.82, "sezgisel": 0.74},
        recommended_approach="Kanıta dayalı temas önerilir.",
        evidence_sources=["user_mirror", "target_analysis"],
        vector_provenance={
            "user": "mirror_truth:hash-abc",
            "target": "osint_investigator:hash-def",
        },
    )
    executor = _executor(["resonance_calc"], profile)

    status = await executor.execute_task({"target_profile": {}}, "task-decision")

    run = status.agent_runs["resonance_calc"]
    assert run.status == "completed"
    assert run.decision_grade is True
    assert run.confidence is not None and run.confidence >= 0.65


# --------------------------------------------------------------------------- #
# 3) DecisionEngine: no-decision koşusu kanıt SAYILMAZ
# --------------------------------------------------------------------------- #
def _run(agent: str, status: str, summary: dict, confidence: float | None = None) -> AgentRun:
    return AgentRun(
        task_id="t", agent_name=agent, status=status,
        output_summary=summary, confidence=confidence,
    )


def test_no_decision_run_is_not_evidence_and_degrades_pipeline():
    engine = DecisionEngine(DecisionConfig.load())

    evidence_run = _run(
        "mirror_truth", "completed",
        {"user_core_frequency": "Analitik-sezgisel", "data_confidence": True},
        confidence=0.8,
    )
    no_decision_run = _run(
        "resonance_calc", "completed_no_decision",
        {"state": "inference_gap", "data_confidence": False, "compatibility_score": 0.0},
        confidence=0.0,
    )

    # Kanıt taşıyan başka bir ajan var -> görev TAMAMLANMADI sayılmaz ama
    # karar-Grade da değil: PARTIALLY_COMPLETED.
    verdict = engine.make_decision({"mirror_truth": evidence_run, "resonance_calc": no_decision_run})
    assert verdict == PipelineStatus.PARTIALLY_COMPLETED

    # Yalnız karar-olmayan koşu varsa: ortada KANIT YOK -> fail-closed.
    verdict = engine.make_decision({"resonance_calc": no_decision_run})
    assert verdict == PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE


def test_no_decision_status_alone_degrades_even_without_summary_flag():
    """Hüküm yalnız `output_summary.data_confidence`'a bakmaz.

    `completed_no_decision` durumu (veya `decision_grade=False`) başlı başına
    "bu koşu karar değil" beyanıdır: özet alanı bu bayrağı taşımasa bile
    DecisionEngine koşuyu kanıt saymaz ve görevi karar-Grade ilan etmez.
    """
    engine = DecisionEngine(DecisionConfig.load())
    evidence_run = _run(
        "mirror_truth", "completed",
        {"user_core_frequency": "Analitik-sezgisel", "data_confidence": True},
    )
    # ÖZETİNDE data_confidence YOK — yalnız koşu durumu/bayrağı konuşuyor.
    bare_run = _run(
        "resonance_calc", "completed_no_decision",
        {"state": "inference_gap", "compatibility_score": 0.0},
    )
    bare_run.decision_grade = False

    assert engine.make_decision({"mirror_truth": evidence_run, "resonance_calc": bare_run}) == (
        PipelineStatus.PARTIALLY_COMPLETED
    )
    assert engine.make_decision({"resonance_calc": bare_run}) == (
        PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE
    )


def test_no_decision_run_is_not_a_failure_either():
    """`completed_no_decision` halted/failed değildir: kritik durdurma tetiklemez."""
    engine = DecisionEngine(DecisionConfig.load())
    run = _run(
        "resonance_calc", "completed_no_decision",
        {"state": "inference_gap", "data_confidence": False},
    )
    evidence_run = _run(
        "mirror_truth", "completed",
        {"user_core_frequency": "Analitik-sezgisel", "data_confidence": True},
    )
    # mirror_truth kritik ajan: onun kanıtı varsa görev kritik durmaz.
    assert engine.make_decision({"mirror_truth": evidence_run, "resonance_calc": run}) in (
        PipelineStatus.PARTIALLY_COMPLETED,
        PipelineStatus.COMPLETED,
    )
    assert engine.make_decision({"mirror_truth": evidence_run, "resonance_calc": run}) != PipelineStatus.HALTED_CRITICAL
