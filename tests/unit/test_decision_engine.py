"""
DecisionEngine ve 5./6. damga (shadow/osint) durum muhasebesi testleri.

Regresyon guvencesi: shadow/osint ajanlari ana dongunun disinda calistigi icin
basarisizliklari daha once status.agent_runs'a yazilmiyor; DecisionEngine
onlari gormuyor ve boru hatti yanlis sekilde "completed" diyebiliyordu.
"""
from datetime import datetime, timezone

import pytest

from agent_core.config_loader import DecisionConfig
from agent_core.domain.memory_models import AgentRun
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.services.decision_engine import DecisionEngine


def _run(status: str, output_summary: dict | None = None) -> AgentRun:
    # [019] state machine: 'completed' kanıt içermedikçe başarı sayılmaz.
    # Gerçekçi kayıtlar output_summary taşır; testlerde varsayılan olarak
    # gerçek kanıt veriyoruz.
    return AgentRun(
        task_id="t", agent_name="x", status=status,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        output_summary=output_summary if output_summary is not None else {"note": "gerçek kanıt"},
    )


@pytest.fixture
def engine():
    cfg = DecisionConfig.load()
    return DecisionEngine(cfg)


def test_all_completed(engine):
    runs = {"a": _run("completed"), "b": _run("completed")}
    assert engine.make_decision(runs) == PipelineStatus.COMPLETED


def test_critical_agent_failure_halts(engine):
    runs = {"mirror_truth": _run("failed"), "b": _run("completed")}
    assert engine.make_decision(runs) == PipelineStatus.HALTED_CRITICAL


def test_non_critical_failure_is_partial(engine):
    # shadow_executor ve osint_investigator graceful_degradation=true
    runs = {
        "shadow_executor": _run("failed"),
        "osint_investigator": _run("failed"),
        "mirror_truth": _run("completed"),
    }
    assert engine.make_decision(runs) == PipelineStatus.PARTIALLY_COMPLETED


def test_config_uses_real_agent_name_shadow_executor(engine):
    """Config anahtari ajan kayit adiyla eslesmeli (shadow_profile DEGIL)."""
    assert "shadow_executor" in engine.config.agents
    assert "shadow_profile" not in engine.config.agents


def test_empty_route_is_insufficient_not_completed(engine):
    """[019] boş rota (hedef+kullanıcı kanıtı yok) asla COMPLETED olamaz."""
    assert engine.make_decision({}) == PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE


def test_placeholder_only_completed_run_is_insufficient(engine):
    """[019] placeholder-şişkin (dolu görünen, kanıt taşımayan) çıktı
    'completed' olsa bile başarı sayılmaz."""
    runs = {
        "cognitive_profiler": _run(
            status="completed",
            output_summary={
                "communication_tone": "unknown",
                "complexity_level": "unknown",
                "humor_style": None,
                "social_orientation": "unknown",
            },
        ),
    }
    assert engine.make_decision(runs) == PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE


def test_completed_with_real_evidence_only_is_completed(engine):
    runs = {
        "mirror_truth": _run("completed"),
        "passion_mapper": _run("completed"),
    }
    assert engine.make_decision(runs) == PipelineStatus.COMPLETED
