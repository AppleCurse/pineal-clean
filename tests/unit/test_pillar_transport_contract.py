"""BOSS-5 — deterministik motor çıktılarının taşınması (sözleşme testi).

Röntgen bulgusu: `frequency_map` … `key_matrix` ve `psychodynamic_depth`
hesaplanıyor, `TaskSnapshot`'a yazılıyor, ama HİÇBİR WS payload'ına girmiyordu
(ne snapshot_update ne result) ve mühür yalnız 7 anahtarlık özeti saklıyordu.
Bu test üç taşıma noktasını da kilitler:
  1) snapshot payload'ı,
  2) result payload'ı,
  3) kanıt zinciri (dolayısıyla mühür).
"""

from __future__ import annotations

import pytest

from agent_core.domain.memory_models import TaskSnapshot

PILLAR_KEYS = (
    "frequency_map",
    "seismos_events",
    "void_map",
    "strata_map",
    "gravity_map",
    "pulse_map",
    "key_matrix",
)


@pytest.fixture(autouse=True)
def _clean_rooms():
    from backend import api

    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()
    yield
    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()


def _snapshot_with_pillars(task_id: str = "op_pillar_1") -> TaskSnapshot:
    snap = TaskSnapshot(task_id=task_id, status="processing")
    for name in PILLAR_KEYS:
        setattr(snap, name, {"status": "OBSERVED", "marker": name})
    snap.pillar_bundle = {"version": "pillar-full-v1", "computed_at": "2026-09-21T00:00:00Z"}
    snap.psychodynamic_depth = {"verdict": "ok", "confidence": 0.9, "channels": {}}
    return snap


def test_pillar_payload_fields_covers_every_computed_field():
    from backend import api

    fields = api._pillar_payload_fields(_snapshot_with_pillars())

    for name in PILLAR_KEYS:
        assert fields[name] == {"status": "OBSERVED", "marker": name}
    assert fields["psychodynamic_depth"]["verdict"] == "ok"
    # `pillar_bundle` yedi raporun TAM kopyasıdır: yayında tekrar edilmez.
    assert "pillar_bundle" not in fields


def test_pillar_payload_fields_is_empty_safe():
    """Sütun verisi yoksa payload'a None yazılır, anahtar uydurulmaz."""
    from backend import api

    fields = api._pillar_payload_fields(TaskSnapshot(task_id="op_empty", status="processing"))

    assert all(fields[name] is None for name in PILLAR_KEYS)
    assert fields["psychodynamic_depth"] is None


@pytest.mark.asyncio
async def test_snapshot_frame_carries_pillars(monkeypatch):
    import json

    from backend import api

    room = api.get_room("boss5-snap")
    sent: list[str] = []

    async def _fake_send_ws(_room, payload):
        sent.append(payload)

    monkeypatch.setattr(api, "_send_ws", _fake_send_ws)

    await api._send_snapshot(room, _snapshot_with_pillars())

    frame = json.loads(sent[-1])
    assert frame["type"] == "snapshot_update"
    assert frame["frequency_map"]["marker"] == "frequency_map"
    assert frame["key_matrix"]["marker"] == "key_matrix"
    assert frame["psychodynamic_depth"]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_result_frame_carries_pillars(monkeypatch):

    from backend import api

    api.get_room("boss5-res")
    captured: list[tuple] = []
    monkeypatch.setattr(api, "_enqueue", lambda client_id, item: captured.append(item))

    snap = _snapshot_with_pillars()
    api.broadcast_result("boss5-res", snap)

    _, payload = captured[-1]
    assert payload["type"] == "result"
    for name in PILLAR_KEYS:
        assert payload[name] == {"status": "OBSERVED", "marker": name}
    assert payload["psychodynamic_depth"]["verdict"] == "ok"
