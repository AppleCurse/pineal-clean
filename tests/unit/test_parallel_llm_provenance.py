"""P0 regression tests for call-id based LLM provenance."""

import asyncio
import json

import pytest
from pydantic import BaseModel

from agent_core.services.llm_gateway import LLMGateway
from agent_core.task_executor import PinealExecutor


class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    usage = None

    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _ConcurrentCompletions:
    async def create(self, *, model, **kwargs):
        # Complete B first so a shared "last call" implementation would point
        # at a different model while A is still running.
        await asyncio.sleep(0.03 if model.endswith("model-a") else 0)
        return _Response(f"answer:{model}")


class _RetryCompletions:
    def __init__(self):
        self.attempts = 0

    async def create(self, **kwargs):
        self.attempts += 1
        if self.attempts == 1:
            raise TimeoutError("temporary timeout")
        return _Response("recovered")


class _Client:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


class _Result(BaseModel):
    data_confidence: bool = True
    fallback_reason: str | None = None


@pytest.mark.asyncio
async def test_concurrent_agents_keep_model_provider_and_call_id_isolated():
    gateway = LLMGateway()
    gateway.local_client = _Client(_ConcurrentCompletions())
    gateway.cache = None

    async def invoke(agent_id: str, model: str):
        with gateway.capture_calls("task-parallel", agent_id) as scope:
            answer = await gateway.query("prompt", model=model)
        return answer, scope

    (answer_a, scope_a), (answer_b, scope_b) = await asyncio.gather(
        invoke("agent-a", "local/model-a"),
        invoke("agent-b", "local/model-b"),
    )

    assert answer_a == "answer:local/model-a"
    assert answer_b == "answer:local/model-b"
    assert len(scope_a.records) == len(scope_b.records) == 1

    call_a = scope_a.records[0]
    call_b = scope_b.records[0]
    required = {
        "call_id", "task_id", "agent_id", "model", "provider", "attempt",
        "cache_hit", "prompt_tokens", "completion_tokens", "cost_usd",
        "started_at", "finished_at", "error",
    }
    assert required <= call_a.keys()
    assert required <= call_b.keys()
    assert call_a["call_id"] != call_b["call_id"]
    assert (call_a["task_id"], call_a["agent_id"], call_a["model"], call_a["provider"]) == (
        "task-parallel", "agent-a", "local/model-a", "local"
    )
    assert (call_b["task_id"], call_b["agent_id"], call_b["model"], call_b["provider"]) == (
        "task-parallel", "agent-b", "local/model-b", "local"
    )

    executor = PinealExecutor()
    executor.llm_gateway = gateway
    provenance_a = executor._provenance_for("agent-a", _Result(), scope_a.records)
    provenance_b = executor._provenance_for("agent-b", _Result(), scope_b.records)
    assert (provenance_a["call_id"], provenance_a["model"]) == (call_a["call_id"], "local/model-a")
    assert (provenance_b["call_id"], provenance_b["model"]) == (call_b["call_id"], "local/model-b")

    evidence_a = executor._evidence_record(
        "agent-a", _Result(), evidence_type="agent_output", llm_calls=scope_a.records
    )
    evidence_b = executor._evidence_record(
        "agent-b", _Result(), evidence_type="agent_output", llm_calls=scope_b.records
    )
    assert evidence_a["call_ids"] == [call_a["call_id"]]
    assert evidence_b["call_ids"] == [call_b["call_id"]]
    json.dumps([evidence_a, evidence_b])


@pytest.mark.asyncio
async def test_retry_chain_preserves_one_call_id_and_final_attempt(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    completions = _RetryCompletions()
    gateway = LLMGateway()
    gateway.local_client = _Client(completions)
    gateway.cache = None

    with gateway.capture_calls("task-retry", "agent-retry") as scope:
        assert await gateway.query("prompt", model="local/retry-model") == "recovered"

    assert completions.attempts == 2
    assert len(scope.records) == 1
    call = scope.records[0]
    assert call["attempt"] == 2
    assert call["error"] is None
    assert scope.call_ids == [call["call_id"]]
