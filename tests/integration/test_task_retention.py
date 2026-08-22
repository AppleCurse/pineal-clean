"""
FAZ 3 / etik çerçeve — görev geçmişi ve KALICI veri silme (retention) sözleşmesi.
"""
import json
import uuid

from fastapi.testclient import TestClient

from backend.api import app


def test_task_lifecycle_list_and_delete(tmp_path):
    cid = f"life_{uuid.uuid4().hex[:8]}"
    task_id = "retention_test_1"
    with TestClient(app) as client:
        # Odanın belleğini geçici dizine yönlendir (repo kirletilmesin)
        from backend.api import get_room
        room = get_room(cid)
        room["executor"].memory.storage_path = str(tmp_path)
        room.setdefault("active_tasks", {})[task_id] = {"task_id": task_id}

        task_id = "retention_test_1"
        mem = tmp_path / f"{task_id}.json"
        mem.write_text(json.dumps({
            "task_id": task_id, "last_updated": "2026-08-22T00:00:00+00:00",
            "evidence": [{"agent": "x"}], "confidence": 0.9,
        }), encoding="utf-8")
        room["active_tasks"][task_id] = {"task_id": task_id}

        # Liste
        r = client.get("/api/tasks", params={"client_id": cid})
        assert r.status_code == 200
        found = [t for t in r.json()["tasks"] if t["task_id"] == task_id]
        assert found and found[0]["evidence_count"] == 1
        assert task_id in r.json()["active_tasks"]

        # Sil
        r = client.delete(f"/api/tasks/{task_id}", params={"client_id": cid})
        assert r.status_code == 200
        body = r.json()
        assert body == {"status": "deleted", "task_id": task_id,
                        "snapshot_removed": True, "memory_file_deleted": True}
        assert not mem.exists(), "kanıt dosyası diskten silinmeli"
        assert task_id not in room["active_tasks"]

        # Tekrar sil → 404 (hata modeliyle)
        r = client.delete(f"/api/tasks/{task_id}", params={"client_id": cid})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"
