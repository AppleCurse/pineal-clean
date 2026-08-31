import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from agent_core.services.canonical_memory import (
    CanonicalMemory,
    MemoryCorruptedError,
    MemoryState,
)
from agent_core.task_executor import PinealExecutor


def test_missing_memory_is_explicitly_empty(tmp_path):
    memory = CanonicalMemory(str(tmp_path))

    inspection = memory.inspect_task_memory("not_created")

    assert inspection == {
        "task_id": "not_created",
        "state": MemoryState.EMPTY.value,
        "data": None,
        "error_code": None,
        "reason": None,
    }
    assert memory.get_task_memory("not_created") == {}


@pytest.mark.parametrize(
    ("raw_content", "reason"),
    [
        ("{not-json", "INVALID_JSON"),
        ("", "EMPTY_FILE"),
        ("[]", "INVALID_ROOT_TYPE"),
        ('{"evidence": {}}', "INVALID_EVIDENCE_TYPE"),
        ('{"task_id": "different", "evidence": []}', "TASK_ID_MISMATCH"),
    ],
)
def test_existing_invalid_memory_is_never_reported_as_empty(tmp_path, raw_content, reason):
    memory = CanonicalMemory(str(tmp_path))
    canonical = tmp_path / "broken.json"
    canonical.write_text(raw_content, encoding="utf-8")

    inspection = memory.inspect_task_memory("broken")

    assert inspection["state"] == MemoryState.CORRUPTED.value
    assert inspection["error_code"] == "MEMORY_CORRUPTED"
    assert inspection["reason"] == reason
    with pytest.raises(MemoryCorruptedError) as raised:
        memory.get_task_memory("broken")
    assert raised.value.error_code == "MEMORY_CORRUPTED"
    assert raised.value.reason == reason


@pytest.mark.asyncio
async def test_normal_merge_refuses_corrupt_memory_and_preserves_exact_bytes(tmp_path):
    memory = CanonicalMemory(str(tmp_path))
    canonical = tmp_path / "recover_me.json"
    corrupt_bytes = b"{not-json\x00forensic-material"
    canonical.write_bytes(corrupt_bytes)

    with pytest.raises(MemoryCorruptedError, match="MEMORY_CORRUPTED"):
        await memory.merge_evidence(
            "recover_me",
            [{"agent": "test", "result": {"confidence": 0.8}}],
        )

    assert canonical.read_bytes() == corrupt_bytes
    assert not list(tmp_path.glob("recover_me.json.corrupt.*"))


@pytest.mark.asyncio
async def test_explicit_recovery_quarantines_original_and_allows_future_merge(tmp_path):
    memory = CanonicalMemory(str(tmp_path))
    canonical = tmp_path / "recover_me.json"
    corrupt_bytes = b"{not-json\x00forensic-material"
    canonical.write_bytes(corrupt_bytes)

    recovery = await memory.quarantine_and_reset("recover_me")

    assert recovery["action"] == "QUARANTINE_AND_RESET"
    assert recovery["previous_state"] == MemoryState.CORRUPTED.value
    assert recovery["state"] == MemoryState.READY.value
    quarantine = tmp_path / recovery["quarantine_path"].split("/")[-1]
    assert quarantine.read_bytes() == corrupt_bytes

    reset = memory.get_task_memory("recover_me")
    assert reset["evidence"] == []
    assert reset["recovery"]["reason"] == "INVALID_JSON"
    assert reset["recovery"]["quarantine_file"] == quarantine.name

    await memory.merge_evidence(
        "recover_me",
        [{"agent": "test", "result": {"confidence": 0.8}}],
    )
    recovered = json.loads(canonical.read_text(encoding="utf-8"))
    assert recovered["evidence"][0]["agent"] == "test"


@pytest.mark.asyncio
async def test_concurrent_corruption_reads_and_merges_all_fail_closed(tmp_path):
    memory = CanonicalMemory(str(tmp_path))
    canonical = tmp_path / "contended.json"
    canonical.write_bytes(b"{broken")

    async def read_once():
        return await asyncio.to_thread(memory.get_task_memory, "contended")

    operations = [read_once() for _ in range(25)] + [
        memory.merge_evidence("contended", [{"agent": str(index)}])
        for index in range(25)
    ]
    results = await asyncio.gather(*operations, return_exceptions=True)

    assert all(isinstance(result, MemoryCorruptedError) for result in results)
    assert canonical.read_bytes() == b"{broken"
    assert not list(tmp_path.glob("contended.json.corrupt.*"))


@pytest.mark.asyncio
async def test_executor_halts_before_analysis_when_canonical_memory_is_corrupt(tmp_path):
    memory = CanonicalMemory(str(tmp_path))
    (tmp_path / "blocked_task.json").write_text("{broken", encoding="utf-8")
    events = []
    executor = PinealExecutor(emit_event_callback=events.append)
    executor.memory = memory
    executor.router.analyze = AsyncMock()

    status = await executor.execute_task({"target_profile": {}}, "blocked_task")

    assert status.status == "halted_critical"
    assert status.halted_reason == "MEMORY_CORRUPTED"
    assert status.telemetry["memory_state"] == MemoryState.CORRUPTED.value
    assert status.telemetry["memory_error_code"] == "MEMORY_CORRUPTED"
    assert status.telemetry["memory_corruption_reason"] == "INVALID_JSON"
    executor.router.analyze.assert_not_awaited()
    assert len(events) == 1
    assert events[0].error_code == "MEMORY_CORRUPTED"
    assert events[0].agent_name == "CanonicalMemory"
