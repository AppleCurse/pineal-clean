"""BOSS-6 — Authentic-vector LLM harcamasının telemetriye bağlanması.

Röntgen bulgusu (ölçüldü): `mirror_truth` ve `human_behavior` ajanları bittikten
sonra `_calculate_authentic_vector` çalışır. Bu çağrılar (tier=1, "ASLA KİBAR
OLMA" promptu) `_capture_llm_calls` kapsamı DIŞINDA yapılıyordu:

    {"mirror_truth": 1, "None": 2, "human_behavior": 1, ...}
                        ^^^^^^^^^
    görev başına 2 çağrı ajan=None, task=None → hiçbir kanıta/koşuya bağlanamaz

Yani harcama gerçekti, iz yoktu. Bu dosya kapsamın geri alınması durumunda KIZAR.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from agent_core.domain.memory_models import TaskSnapshot
from agent_core.services.llm_gateway import LLMCallScope, _active_call_scope
from agent_core.task_executor import PinealExecutor


class DummyResult(BaseModel):
    compatibility_score: float = 0.9


class DummyCheck(BaseModel):
    confidence: float = 0.9
    is_suspicious: bool = False
    reason: str = ""


class _ScopedGateway:
    """Gerçek gateway'in aktivite sözleşmesini taşıyan sahte taşıyıcı.

    `capture_calls` gerçek `_active_call_scope` contextvar'ını kullanır; böylece
    "kapsam içinde mi çağrıldı" sorusu testte de gerçek kodla aynı şekilde
    yanıtlanır.
    """

    def __init__(self):
        self.calls: list[dict] = []

    @contextmanager
    def capture_calls(self, task_id, agent_id):
        scope = LLMCallScope(task_id=task_id, agent_id=agent_id)
        token = _active_call_scope.set(scope)
        try:
            yield scope
        finally:
            _active_call_scope.reset(token)

    def _record(self, kind: str) -> None:
        scope = _active_call_scope.get()
        entry = {
            "call_id": f"call-{len(self.calls)}",
            "kind": kind,
            "model": "stub",
            "provider": "stub",
            "agent_id": getattr(scope, "agent_id", None),
            "task_id": getattr(scope, "task_id", None),
        }
        self.calls.append(entry)
        if scope is not None:
            scope.records.append(entry)

    async def query_json(self, prompt, schema=None, *a, **k):
        self._record("query_json")
        return schema(depth=0.8, energy=0.6, achilles_heel="x", core_wound="y", dark_detail="z")

    async def query(self, prompt, *a, **k):
        self._record("query")
        return "not"


@pytest.fixture
def executor():
    e = PinealExecutor()
    e.llm_gateway = _ScopedGateway()

    class Route:
        agents = ["mirror_truth", "human_behavior"]

    e.router = MagicMock()
    e.router.analyze = AsyncMock(return_value=Route())
    e.uncertainty = MagicMock()
    e.uncertainty.evaluate.return_value = DummyCheck()
    e.memory = MagicMock()
    e.memory.merge_evidence = AsyncMock()
    e.injector = MagicMock()
    e.injector.fetch_active_rules.return_value = {}
    for name in e.agents:
        e.agents[name] = MagicMock()
        e.agents[name].execute = AsyncMock(return_value=DummyResult())
    e._download_images = AsyncMock(return_value=[])
    return e


@pytest.mark.asyncio
async def test_authentic_vector_calls_are_attributed_to_the_producing_agent(executor):
    status = await executor.execute_task({}, "task_b6")
    assert isinstance(status, TaskSnapshot)

    gw = executor.llm_gateway
    # Görev başına iki vektör çağrısı: biri kullanıcı, biri hedef profili.
    assert len(gw.calls) == 2, gw.calls
    assert [c["agent_id"] for c in gw.calls] == ["authentic_vector:user", "authentic_vector:target"]
    assert all(c["task_id"] == "task_b6" for c in gw.calls), "çağrı göreve bağlanmadı"
    # Ajan adı boş kalan "sahipsiz" kayıt kalmamalı.
    assert not [c for c in gw.calls if c["agent_id"] is None]

    mirror = status.agent_runs["mirror_truth"]
    target = status.agent_runs["human_behavior"]
    assert [r["agent_id"] for r in mirror.output_summary["_aux_llm_calls"]] == ["authentic_vector:user"]
    assert [r["agent_id"] for r in target.output_summary["_aux_llm_calls"]] == ["authentic_vector:target"]
    # Vektör çağrıları koşunun call_ids listesine de bağlanmalı; aksi hâlde
    # kanıt zinciri "bu koşuda kaç çağrı yapıldı" sorusunu eksik yanıtlar.
    assert mirror.call_ids == ["call-0"], mirror.call_ids
    assert target.call_ids == ["call-1"], target.call_ids


def test_attach_vector_calls_is_empty_safe():
    """Kayıt yoksa koşu raporuna boş alan eklenmez (uydurma iz yok)."""

    class Run:
        call_ids: list = []

    run = Run()
    PinealExecutor._attach_vector_calls(run, [])

    assert getattr(run, "call_ids") == []
    assert getattr(run, "output_summary", None) is None
