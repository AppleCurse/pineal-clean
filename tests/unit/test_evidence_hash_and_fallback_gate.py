from pydantic import BaseModel

from agent_core.services.uncertainty_engine import UncertaintyEngine
from agent_core.task_executor import PinealExecutor


class Result(BaseModel):
    value: str
    confidence: float = 0.9
    data_confidence: bool = False


def test_step_hash_is_result_sensitive_and_not_placeholder():
    assert PinealExecutor._hash_evidence_result(Result(value="a")) != PinealExecutor._hash_evidence_result(Result(value="b"))
    assert PinealExecutor._hash_evidence_result(Result(value="a")) != "HASH"


def test_unavailable_data_is_never_safe_uncertainty():
    report = UncertaintyEngine().evaluate(Result(value="fallback"), "passion_mapper")
    assert report.is_suspicious is True
    assert report.confidence == 0.0
