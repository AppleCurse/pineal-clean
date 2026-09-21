"""[BOSS-11] WS çerçeve sözleşmesi — tek serileştirme + görünür çerçeve hatası.

Röntgen bulgusu: mühür (canonical memory) `json.dumps(..., default=str)` ile
yazarken WS çerçeveleri çıplak `json.dumps` kullanıyordu. `model_dump()` bugün
JSON-uyumlu görünse de tek bir Enum/datetime alanı eklendiğinde çerçeve
üretimi patlar; `_room_sender` bunu yalnız print edip yutuyordu — kaybolan
çerçeve telemetride görünmüyordu.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from enum import Enum

import pytest

from agent_core.domain.memory_models import TaskSnapshot


@pytest.fixture(autouse=True)
def _clean_rooms():
    from backend import api

    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()
    yield
    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()


class _Color(Enum):
    RED = "red"


def test_ws_json_shares_the_seal_contract():
    """Mühürle aynı sözleşme: JSON'a çevrilemeyen değer `str()` ile yazılır."""
    from backend import api

    frame = api._ws_json({"at": datetime(2026, 9, 21, tzinfo=timezone.utc), "color": _Color.RED})

    decoded = json.loads(frame)
    assert decoded["at"].startswith("2026-09-21")
    assert decoded["color"] in ("_Color.RED", "red"), decoded["color"]


@pytest.mark.asyncio
async def test_snapshot_frame_survives_non_json_payload(monkeypatch):
    """Enum/datetime içeren telemetri çerçeveyi düşürmemeli."""
    from backend import api

    room = api.get_room("boss11-snap")
    sent: list[str] = []

    async def _capture(_room, payload):
        sent.append(payload)

    monkeypatch.setattr(api, "_send_ws", _capture)

    snap = TaskSnapshot(task_id="op_b11", status="processing", telemetry={"at": datetime.now(timezone.utc)})
    await api._send_snapshot(room, snap)

    frame = json.loads(sent[-1])
    assert frame["type"] == "snapshot_update"
    assert frame["telemetry"]["at"]


def test_frame_error_is_recorded_in_delivery_report():
    """Çerçeve hatası sessiz kalmaz: sayaç + örnek + DEGRADED durumu."""
    from backend import api

    room = api.get_room("boss11-err")
    api._record_frame_error(room, "snapshot", ValueError("serialization boom"))

    delivery = api._delivery_status(room)
    assert delivery["state"] == "DEGRADED_FRAME_ERROR"
    assert delivery["frame_errors_total"] == 1
    assert delivery["frame_errors_by_kind"] == {"snapshot": 1}
    assert "serialization boom" in room["frame_error_samples"][-1]


@pytest.mark.asyncio
async def test_room_sender_records_error_instead_of_silently_swallowing(monkeypatch):
    from backend import api

    room = api.get_room("boss11-sender")

    async def _boom(_room, _payload):
        raise RuntimeError("frame blow-up")

    monkeypatch.setattr(api, "_send_snapshot", _boom)

    sender = asyncio.create_task(api._room_sender(room))
    room["queue"].put_nowait(("snapshot", TaskSnapshot(task_id="op_b11", status="processing")))
    for _ in range(20):
        await asyncio.sleep(0)
        if room.get("telemetry_delivery", {}).get("frame_errors_total"):
            break
    sender.cancel()
    with pytest.raises(asyncio.CancelledError):
        await sender

    delivery = api._delivery_status(room)
    assert delivery["frame_errors_total"] == 1
    assert delivery["frame_errors_by_kind"] == {"snapshot": 1}
    assert delivery["state"] == "DEGRADED_FRAME_ERROR"


@pytest.mark.asyncio
async def test_result_frame_uses_the_same_contract(monkeypatch):
    from backend import api

    api.get_room("boss11-result")
    captured: list[tuple] = []
    monkeypatch.setattr(api, "_enqueue", lambda client_id, item: captured.append(item))

    snap = TaskSnapshot(task_id="op_b11r", status="completed", telemetry={"at": datetime.now(timezone.utc)})
    api.broadcast_result("boss11-result", snap)

    _, payload = captured[-1]
    assert payload["type"] == "result"
    # Çerçeve _ws_json'dan geçmeli: sözlükte datetime yaşayabilir, gönderimde çevrilir
    # (eski çıplak json.dumps burada TypeError verirdi).
    decoded = json.loads(api._ws_json(payload))
    assert decoded["type"] == "result"
    assert decoded["telemetry"]["at"].startswith("2026-")
