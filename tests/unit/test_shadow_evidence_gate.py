"""[019] ShadowExecutor kanıt kapısı: boş hedefte sahte shadow profili üretilmez.

Kural: hedef bio/posts/username/name/images yoksa strateji, mesaj ve NLP
dizisi ÜRETİLEMEZ; sonuç data_confidence=False + confidence=0.0 olarak
kaydedilir ve DecisionEngine onu kanıt saymaz.
"""
import pytest

from agent_core.config_loader import DecisionConfig
from agent_core.domain.memory_models import AgentRun
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.services.decision_engine import DecisionEngine
from agent_core.shadow.shadow_executor import ShadowExecutor


@pytest.mark.asyncio
async def test_shadow_empty_target_produces_no_fabricated_profile():
    executor = ShadowExecutor()
    result = await executor.execute({"target_profile": {}, "user_profile": {}})

    assert result.data_confidence is False
    assert result.confidence == 0.0
    assert result.fallback_reason == "target_evidence_unavailable"
    assert result.strategy == "unavailable"
    assert result.message == ""
    assert result.nlp_sequence == []


@pytest.mark.asyncio
async def test_shadow_with_real_target_still_produces_profile():
    executor = ShadowExecutor()
    result = await executor.execute({
        "target_profile": {
            "bio": "Mükemmel, mükemmel, mükemmel, mükemmel, eşsiz, eşsiz, olağanüstü, benzersiz, seçilmiş. Mükemmeliyetçi ve hırslı bir lider.",
            "posts": ["Başarı tek seçenektir.", "Kontrol bende."],
        },
        "user_profile": {"rituals": ["kahve"], "music": "klasik", "envies": "derin bağ"},
        "target_beliefs": ["kontrolü elde tutmak"],
    })
    assert result.data_confidence is True
    assert isinstance(result.message, str) and len(result.message) > 0
    assert result.strategy != "unavailable"
    assert len(result.nlp_sequence) == 3


def test_unavailable_shadow_run_is_not_pipeline_evidence():
    """data_confidence=False + target_evidence_unavailable shadow kaydı
    'completed' görünse bile kanıt sayılmaz."""
    config = DecisionConfig.load()
    result = DecisionEngine(config).make_decision({
        "shadow_executor": AgentRun(
            task_id="x", agent_name="shadow_executor", status="completed",
            confidence=None,
            warnings=["target_evidence_unavailable"],
            output_summary={
                "message": "",
                "strategy": "unavailable",
                "nlp_sequence": [],
                "dark_profile": {"machiavellianism": 0.0, "exploitability": 0.0},
                "data_confidence": False,
            },
        ),
        "osint_investigator": AgentRun(
            task_id="y", agent_name="osint_investigator", status="completed",
            confidence=None,
            warnings=["no_target_identity"],
            output_summary={
                "associated_platforms": [],
                "digital_footprint_score": 0.0,
                "data_confidence": False,
            },
        ),
    })
    assert result == PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE
