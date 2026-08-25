from agent_core.domain.memory_models import AgentRun
from agent_core.task_executor import PinealExecutor


def test_holistic_confidence_uses_measured_completed_profile_confidences_only():
    runs = {
        "passion_mapper": AgentRun(task_id="x", agent_name="passion_mapper", status="completed", confidence=0.8),
        "friction_detector": AgentRun(task_id="x", agent_name="friction_detector", status="completed", confidence=0.6),
        "cognitive_profiler": AgentRun(task_id="x", agent_name="cognitive_profiler", status="failed", confidence=0.99),
        "shadow_executor": AgentRun(task_id="x", agent_name="shadow_executor", status="completed", confidence=0.99),
    }

    assert PinealExecutor._holistic_confidence(runs) == 0.7


def test_holistic_confidence_is_zero_when_no_profile_confidence_is_measured():
    assert PinealExecutor._holistic_confidence({}) == 0.0
