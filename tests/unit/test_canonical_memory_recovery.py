import json

import pytest

from agent_core.services.canonical_memory import CanonicalMemory


@pytest.mark.asyncio
async def test_merge_recovers_from_corrupt_memory_without_losing_original(tmp_path):
    memory = CanonicalMemory(str(tmp_path))
    broken = tmp_path / "recover_me.json"
    broken.write_text("{not-json", encoding="utf-8")

    await memory.merge_evidence("recover_me", [{"agent": "test", "result": {"confidence": 0.8}}])

    recovered = json.loads(broken.read_text(encoding="utf-8"))
    assert recovered["evidence"][0]["agent"] == "test"
    assert list(tmp_path.glob("recover_me.json.corrupt.*"))
