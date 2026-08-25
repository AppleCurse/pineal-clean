from agent_core.config_loader import DecisionConfig
from agent_core.domain.memory_models import AgentRun
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.services.decision_engine import DecisionEngine


def test_unavailable_completed_agent_cannot_make_pipeline_completed():
    config = DecisionConfig.load()
    result = DecisionEngine(config).make_decision({
        "osint_investigator": AgentRun(
            task_id="x", agent_name="osint_investigator", status="completed",
            confidence=None, warnings=["provider_credentials_unavailable"],
        )
    })
    assert result == PipelineStatus.PARTIALLY_COMPLETED
