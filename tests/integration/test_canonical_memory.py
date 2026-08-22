import pytest
import os
import json
import tempfile
import asyncio
from agent_core.services.canonical_memory import CanonicalMemory

@pytest.fixture
def memory_service():
    temp_dir = tempfile.mkdtemp()
    mem = CanonicalMemory(storage_path=temp_dir)
    yield mem
    # Cleanup
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            os.remove(os.path.join(root, f))
    os.rmdir(temp_dir)

@pytest.mark.asyncio
async def test_canonical_memory_write_read(memory_service):
    task_id = "test_task_1"
    evidence = {"target_authentic_vector": {"depth": 0.8}}
    
    await memory_service.merge_evidence(task_id, [evidence])
    
    data = memory_service.get_task_memory(task_id)
    assert data["evidence"][0]["target_authentic_vector"]["depth"] == 0.8

@pytest.mark.asyncio
async def test_canonical_memory_overwrite(memory_service):
    task_id = "test_task_overwrite"
    await memory_service.merge_evidence(task_id, [{"key1": "val1"}])
    
    # Merge should update existing
    await memory_service.merge_evidence(task_id, [{"key2": "val2"}])
    
    data = memory_service.get_task_memory(task_id)
    assert data["evidence"][0]["key1"] == "val1"
    assert data["evidence"][1]["key2"] == "val2"

@pytest.mark.asyncio
async def test_canonical_memory_missing_file(memory_service):
    data = memory_service.get_task_memory("non_existent_task")
    assert data == {}

@pytest.mark.asyncio
async def test_canonical_memory_corrupted_json(memory_service):
    task_id = "corrupted_task"
    file_path = os.path.join(memory_service.storage_path, f"{task_id}.json")
    
    with open(file_path, "w") as f:
        f.write("{invalid_json:")
        
    # The current implementation returns {} if json decoding fails
    data = memory_service.get_task_memory(task_id)
    assert data == {}
