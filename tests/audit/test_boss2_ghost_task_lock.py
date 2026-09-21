"""BOSS-2 — Hayalet görev / kalıcı 503 kilidi REGRESYON KORUMASI.

Röntgen bulgusu (ölçüldü): `active_tasks` kaydı YALNIZ `_send_snapshot` ile
yazılır. Görev zaman aşımına uğradığında/iptal edildiğinde snapshot "processing"
olarak kalıyor, `_prune_room_stale_state` terminal olmayan kaydı bilinçli olarak
silmiyor (bkz. [AUDIT N1]) ve `_active_tasks_full` odayı doygun sayıyordu.

Gerçek koşuda ölçüm (ölçek: tavan 2, 3 askıda görev):
    active_tasks: 3 kayıt, hepsi "processing"
    retention sweep sonrası: 3 kayıt, hepsi "processing"   ← değişmedi
    oda 'dolu' mu: sweep öncesi=True sonrası=True          ← KALICI 503

Bu dosya korumanın geri alınması durumunda KIZAR.
"""

from __future__ import annotations

import time

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


def _room_with_snapshot(status: str = "processing", task_id: str = "op_ghost_1"):
    from backend import api

    room = api.get_room("boss2-ghost")
    snap = TaskSnapshot(task_id=task_id, status=status)
    room.setdefault("active_tasks", {})[task_id] = snap
    room.setdefault("_active_tasks_ts", {})[task_id] = time.monotonic()
    return room, snap


def test_finished_mission_is_marked_terminal_and_room_unblocks():
    """Biten görev terminal işaretlenir; oda doygunluktan çıkar."""
    from backend import api

    room, snap = _room_with_snapshot()
    room["_finished_missions"] = {snap.task_id}

    api._finalize_finished_missions(room)

    assert api._snapshot_status(snap) == "failed", "hayalet kayıt terminal işaretlenmedi"
    assert api._active_tasks_full(room) is False, "oda hâlâ doygun görünüyor"


def test_timed_out_mission_does_not_lock_room_past_cap(monkeypatch):
    """Tavan aşıldığında bile hayaletler sayılmaz → kalıcı 503 oluşmaz."""
    from backend import api

    room = api.get_room("boss2-cap")
    room["active_tasks"] = {}
    room["_active_tasks_ts"] = {}
    cap = api._ROOM_ACTIVE_TASKS_CAP
    finished = set()
    for i in range(cap + 3):
        tid = f"op_timeout_{i:03d}"
        room["active_tasks"][tid] = TaskSnapshot(task_id=tid, status="processing")
        room["_active_tasks_ts"][tid] = time.monotonic()
        finished.add(tid)
    room["_finished_missions"] = finished

    api._finalize_finished_missions(room)

    assert all(
        api._snapshot_status(s) in api._TERMINAL_PIPELINE_STATES
        for s in room["active_tasks"].values()
    ), "zaman aşımına uğrayan görevler terminal işaretlenmedi"
    assert api._active_tasks_full(room) is False


@pytest.mark.parametrize(
    "real_status",
    ["completed", "partially_completed", "halted_evidence", "halted_critical"],
)
def test_real_terminal_status_is_never_overwritten(real_status):
    """Normal tamamlanan görevin gerçek durumu 'failed'a ezilmez."""
    from backend import api

    room, snap = _room_with_snapshot(status=real_status)
    room["_finished_missions"] = {snap.task_id}

    api._finalize_finished_missions(room)

    assert api._snapshot_status(snap) == real_status


def test_unknown_snapshot_without_finish_signal_is_untouched():
    """Kaydı olmayan (mission_tasks'a hiç girmemiş) iş akışları YANLIŞLIKLA
    'failed' işaretlenmez — yoksa canlı bir görev erken ölü ilan edilirdi."""
    from backend import api

    room, snap = _room_with_snapshot()
    assert "_finished_missions" not in room or not room["_finished_missions"]

    api._finalize_finished_missions(room)

    assert api._snapshot_status(snap) == "processing"


def test_running_mission_is_not_finalized():
    """Hâlâ çalışan görev (mission_tasks'ta canlı) terminal işaretlenmez."""
    from backend import api

    room, snap = _room_with_snapshot()
    room["mission_tasks"] = {snap.task_id: object()}

    api._finalize_finished_missions(room)

    assert api._snapshot_status(snap) == "processing"


def test_done_callback_marks_snapshot_terminal():
    """`_on_mission_done` yolu: görev bitti → kayıt kapanır, kuyruk temizlenir."""
    from backend import api

    room, snap = _room_with_snapshot()
    room["mission_tasks"] = {snap.task_id: object()}
    room["_finished_missions"] = set()

    # done_callback'in yaptığı iki iş: kaydı düşür + finalize et
    room["mission_tasks"].pop(snap.task_id, None)
    room["_finished_missions"].add(snap.task_id)
    api._finalize_finished_missions(room)

    assert api._snapshot_status(snap) == "failed"
    assert not room["_finished_missions"], "kapanan görev izleme kümesinden düşmedi"


def test_prune_sweep_also_finalizes_and_can_trim():
    """Retention sweep terminal kayıtları düşürebilir (hayalet artık terminal)."""
    from backend import api

    room = api.get_room("boss2-prune")
    room["active_tasks"] = {}
    room["_active_tasks_ts"] = {}
    finished = set()
    for i in range(4):
        tid = f"op_sweep_{i}"
        room["active_tasks"][tid] = TaskSnapshot(task_id=tid, status="processing")
        # Not: retention `time.monotonic()` tabanlıdır; 0.0 konteynerin
        # uptime'ı kadardır ve 1800 sn'den küçük olabilir. Gerçekten eski
        # kayıt simüle edilir:
        room["_active_tasks_ts"][tid] = time.monotonic() - 2000.0
        finished.add(tid)
    room["_finished_missions"] = finished
    room["_stale_prune_ts"] = 0.0

    api._prune_room_stale_state(room)

    assert all(
        api._snapshot_status(s) in api._TERMINAL_PIPELINE_STATES
        for s in room["active_tasks"].values()
    )
    assert len(room["active_tasks"]) < 4, "sweep terminal kayıtları düşürmedi"


def test_broadcast_result_error_closes_room_record():
    """Terminal hata bildirimi (max deneme aşıldı vb.) oda kaydını da kapatır."""
    from backend import api

    room, snap = _room_with_snapshot(status="processing")

    api.broadcast_result_error("boss2-ghost", "failed", "MAKSİMUM DENEME AŞILDI", snap.task_id)

    assert api._snapshot_status(snap) == "failed"
    assert api._active_tasks_full(room) is False


def test_broadcast_result_error_ignores_unknown_task():
    """Bilinmeyen task_id sessizce yok sayılır (regresyon: KeyError yok)."""
    from backend import api

    room, snap = _room_with_snapshot(status="processing")

    api.broadcast_result_error("boss2-ghost", "failed", "yok", "op_baska_gorev")

    assert api._snapshot_status(snap) == "processing"
