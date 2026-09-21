"""[BOSS-8] Ajan başına zaman sınırı ve timeout'un terminal raporlanması.

Röntgen bulgusu: hiçbir ajan için duvar saati sınırı yoktu. Tek ajanın LLM
zinciri teorik en kötüde 3 model x 3 taşıma x 45s = 405s sürebiliyordu; görev
bütçesi 300s olduğu için görev iptal edilir, `execute_task` BAŞTAN koşardı
(PINEAL_TASK_MAX_ATTEMPTS=3) — aynı darboğaz 3 kez faturalanırdı.

Bu dosya iki davranışı kilitler:
  1) Ajan kendi sınırını aşarsa kesilir ve "timed_out" olarak raporlanır.
  2) Görev bütçesi dolduğunda görev baştan başlatılmaz; kısmi kanıt yayınlanır.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from agent_core.config_loader import DecisionConfig
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.task_executor import AgentTimeoutError, PinealExecutor


class DummyResult(BaseModel):
    compatibility_score: float = 0.9


class DummyCheck(BaseModel):
    confidence: float = 0.9
    is_suspicious: bool = False
    reason: str = ""


@pytest.fixture
def executor():
    e = PinealExecutor()
    e.llm_gateway = MagicMock()
    e.llm_gateway.query = AsyncMock(return_value="note")

    class Route:
        agents = ["human_behavior", "mirror_truth"]

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
async def test_stuck_agent_is_cut_off_and_labelled(executor, monkeypatch):
    """Takılan ajan görev bütçesini yemez: kendi sınırında kesilir."""
    # Ajan sınırı 0.05s; ajan 5s takılı kalıyor.
    monkeypatch.setattr(
        DecisionConfig, "get_agent_config",
        lambda self, name: MagicMock(
            min_llm_confidence=0.65, graceful_degradation=True,
            timeout_seconds=0.05 if name == "human_behavior" else 0.0,
            field_weights={}, min_data_score=0.6,
        ),
    )
    stuck = asyncio.Event()

    async def _hang(*_args, **_kwargs):
        await asyncio.wait_for(stuck.wait(), timeout=5)
        return DummyResult()

    executor.agents["human_behavior"].execute = AsyncMock(side_effect=_hang)
    e = executor
    e.agents["human_behavior"].AGENT_NAME = "human_behavior"

    status = await e.execute_task({}, "task_b8_timeout")

    run = status.agent_runs["human_behavior"]
    assert run.status == "timed_out", run.status
    assert run.error_code == "AGENT_TIMEOUT"
    assert "sınırını aştı" in (run.error_message or "")
    # Diğer ajan koşmaya devam etti: tek takılan ajan görevi çökertmez.
    assert status.agent_runs["mirror_truth"].status == "completed"
    stuck.set()


@pytest.mark.asyncio
async def test_no_limit_config_keeps_old_behaviour(executor):
    """Sınır 0 ise davranış eskisi gibi (regresyon koruması)."""
    result = await PinealExecutor._bounded(asyncio.sleep(0, result="ok"), 0, "x")
    assert result == "ok"


@pytest.mark.asyncio
async def test_bounded_raises_agent_timeout_error():
    with pytest.raises(AgentTimeoutError) as exc:
        await PinealExecutor._bounded(asyncio.sleep(5), 0.01, "yavaş_ajan")
    assert "yavaş_ajan" in str(exc.value)


def test_pipeline_status_has_distinct_timed_out_state():
    """Timeout 'failed' ile karıştırılamaz: ayrı terminal durum."""
    assert PipelineStatus.TIMED_OUT.value == "timed_out"
    assert PipelineStatus.TIMED_OUT != PipelineStatus.FAILED


@pytest.mark.asyncio
async def test_mission_timeout_does_not_restart_and_publishes_partial(monkeypatch):
    """Görev bütçesi dolduğunda: tek terminal bildirim + kısmi kanıt, yeniden koşma yok."""
    from backend import api

    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()
    room = api.get_room("boss8-timeout")
    from agent_core.domain.memory_models import TaskSnapshot

    partial = TaskSnapshot(task_id="op_b8", status="processing", completed_agents=["mirror_truth"])
    room.setdefault("active_tasks", {})["op_b8"] = partial

    published: list = []
    monkeypatch.setattr(api, "broadcast_result", lambda client_id, res: published.append(res))
    logs: list = []
    monkeypatch.setattr(api, "broadcast_log", lambda client_id, level, msg: logs.append(msg))
    errors: list = []
    monkeypatch.setattr(
        api, "broadcast_result_error",
        lambda client_id, status, msg, task_id=None: errors.append((status, task_id)),
    )

    api._finalize_timed_out_mission("boss8-timeout", "op_b8", 300)

    assert published and published[0].status is PipelineStatus.TIMED_OUT
    assert api._active_tasks_full(room) is False, "timeout kaydı odayı kilitlememeli"
    assert errors and errors[0][0] == "timed_out" and errors[0][1] == "op_b8"
    assert any("baştan başlatılmadı" in msg for msg in logs)


def test_timed_out_is_terminal_and_not_rewritten_to_failed():
    """Ölçülen hata: terminal kümesinde olmadığı için timed_out 'failed'a eziliyordu."""
    from backend import api
    from agent_core.domain.memory_models import TaskSnapshot

    assert "timed_out" in api._TERMINAL_PIPELINE_STATES
    room = api.get_room("boss8-terminal")
    snap = TaskSnapshot(task_id="op_b8t", status="processing")
    room.setdefault("active_tasks", {})["op_b8t"] = snap

    api._close_active_task(room, "op_b8t", PipelineStatus.TIMED_OUT.value)

    assert api._snapshot_status(snap) == "timed_out"
    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()
