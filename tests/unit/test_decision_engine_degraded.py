from agent_core.config_loader import DecisionConfig
from agent_core.domain.memory_models import AgentRun
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.services.decision_engine import DecisionEngine


def test_unavailable_warning_with_real_evidence_is_partial():
    """Unavailable uyarısı + gerçek kanıt -> PARTIALLY_COMPLETED."""
    config = DecisionConfig.load()
    result = DecisionEngine(config).make_decision({
        "osint_investigator": AgentRun(
            task_id="x", agent_name="osint_investigator", status="completed",
            confidence=None, warnings=["provider_credentials_unavailable"],
            output_summary={"associated_platforms": ["instagram"]},
        )
    })
    assert result == PipelineStatus.PARTIALLY_COMPLETED


def test_unavailable_without_evidence_is_insufficient():
    """Unavailable uyarısı + sıfır kanıt -> COMPLETED değil, INSUFFICIENT."""
    config = DecisionConfig.load()
    result = DecisionEngine(config).make_decision({
        "osint_investigator": AgentRun(
            task_id="x", agent_name="osint_investigator", status="completed",
            confidence=None, warnings=["provider_credentials_unavailable"],
            output_summary={},
        )
    })
    assert result == PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE
