"""3. Göz denetimi (2026-09-06) — kapatılan bulguların REGRESYON KORUMASI.

Kapsam:
  R1  Oda-özel sözlüklerin süresiz büyümesi (lifecycle/active_tasks/events/interventions)
  R3  Identifier uzunluk sınırı eksik giriş noktaları (ChatPayload.task_id, cancel/halt)
  R4  P1-6: profil-dışı URL'lerin hedef kullanıcı sanılması (scrape guard)
  R5  P2-9: bozuk learnings.json -> kalıcı 500 (atomik yazım + yedek)
  R6  P1-7: evaluate_confidence anti-halüsinasyon kapısı (üretimde çağrılır)

Her test mutasyon dostudur: ilgili koruma geri alınınca KIZAR.
"""

from __future__ import annotations

import json
import os
import time

import pytest

# --------------------------------------------------------------------------
# R1  TaskLifecycleRegistry — retention sweep
# --------------------------------------------------------------------------
def test_lifecycle_sweep_drops_stale_terminal_runs():
    from agent_core.services.task_lifecycle import TaskLifecycleRegistry

    reg = TaskLifecycleRegistry()
    reg.retention_seconds = 60.0
    now = time.monotonic()

    reg.transition("gorev-terminal", "processing")
    reg.transition("gorev-terminal", "completed")
    reg.transition("gorev-taze", "processing")
    reg.transition("gorev-taze", "completed")
    # terminal run'ı yaşlandır
    reg._runs["gorev-terminal"].last_activity = now - 120

    reg._last_sweep = 0.0
    removed = reg.sweep(now, live_task_ids=set())

    assert removed == 1
    assert "gorev-terminal" not in reg._runs, "eski terminal run geri kazanılmadı"
    assert "gorev-taze" in reg._runs, "taze terminal run yanlışlıkla düşürüldü"


def test_lifecycle_sweep_keeps_live_active_runs():
    from agent_core.services.task_lifecycle import TaskLifecycleRegistry

    now = time.monotonic()
    # canlı görev: yaşlı da olsa düşmez
    reg = TaskLifecycleRegistry()
    reg.retention_seconds = 60.0
    reg.transition("canli", "processing")
    reg._runs["canli"].last_activity = now - 5_000
    reg._last_sweep = 0.0
    reg.sweep(now, live_task_ids={"canli"})
    assert "canli" in reg._runs, "canlı görevin run'ı sweep ile düşürüldü"

    # askıda kalmış (mission_tasks'te olmayan) eski ACTIVE run: düşer
    reg2 = TaskLifecycleRegistry()
    reg2.retention_seconds = 60.0
    reg2.transition("askida", "processing")
    reg2._runs["askida"].last_activity = now - 5_000
    reg2._last_sweep = 0.0
    reg2.sweep(now, live_task_ids=set())
    assert "askida" not in reg2._runs, "askıda kalmış eski run geri kazanılmadı"

    # live_task_ids=None -> muhafazakar: ACTIVE'ye hiç dokunulmaz
    reg3 = TaskLifecycleRegistry()
    reg3.retention_seconds = 60.0
    reg3.transition("korunur", "processing")
    reg3._runs["korunur"].last_activity = now - 5_000
    reg3._last_sweep = 0.0
    reg3.sweep(now, live_task_ids=None)
    assert "korunur" in reg3._runs, "live kümesi yokken ACTIVE run'a dokunuldu"


def test_lifecycle_sweep_is_throttled():
    from agent_core.services.task_lifecycle import TaskLifecycleRegistry

    reg = TaskLifecycleRegistry()
    reg.retention_seconds = 60.0
    now = time.monotonic()
    reg.transition("t", "processing")
    reg.transition("t", "completed")
    reg._runs["t"].last_activity = now - 120

    reg._last_sweep = now  # az önce süpürülmüş
    assert reg.sweep(now) == 0
    assert "t" in reg._runs, "throttle'a rağmen süpürme çalıştı"


# --------------------------------------------------------------------------
# R1  Oda-düzeyi yapılar: active_tasks / interventions / events
# --------------------------------------------------------------------------
class _Snap:
    def __init__(self, task_id: str, status: str):
        self.task_id = task_id
        self.status = status


def _fresh_room(client_id: str):
    from backend import api
    api.app.state.rooms.clear()
    api._rooms_last_seen.clear()
    room = api.get_room(client_id)
    return api, room


def test_room_active_tasks_are_bounded_by_cap():
    api, room = _fresh_room("r1-cap")
    try:
        room["active_tasks"] = {}
        room["_active_tasks_ts"] = {}
        for i in range(300):
            room["active_tasks"][f"t{i}"] = _Snap(f"t{i}", "completed")
            room["_active_tasks_ts"][f"t{i}"] = time.monotonic()
        room["_stale_prune_ts"] = 0.0
        api._prune_room_stale_state(room)
        assert len(room["active_tasks"]) <= api._ROOM_ACTIVE_TASKS_CAP, (
            f"{len(room['active_tasks'])} terminal snapshot kaldı; tavan uygulanmadı"
        )
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


def test_room_active_tasks_terminal_pruned_by_retention():
    api, room = _fresh_room("r1-retention")
    try:
        room["active_tasks"] = {}
        room["_active_tasks_ts"] = {}
        reg = api._lifecycle(room)
        old = time.monotonic() - (reg.retention_seconds + 10)
        room["active_tasks"]["eski-terminal"] = _Snap("eski-terminal", "completed")
        room["_active_tasks_ts"]["eski-terminal"] = old
        room["active_tasks"]["yeni-aktif"] = _Snap("yeni-aktif", "processing")
        room["_active_tasks_ts"]["yeni-aktif"] = time.monotonic()
        room["_stale_prune_ts"] = 0.0
        api._prune_room_stale_state(room)
        assert "eski-terminal" not in room["active_tasks"], "retension dolmuş terminal snapshot kalıyor"
        assert "yeni-aktif" in room["active_tasks"], "aktif görevin snapshot'ı yanlışlıkla düştü"
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


def test_room_interventions_are_capped():
    api, room = _fresh_room("r1-interv")
    try:
        room["interventions"] = [{"i": i} for i in range(600)]
        room["_stale_prune_ts"] = 0.0
        api._prune_room_stale_state(room)
        assert len(room["interventions"]) <= api._ROOM_INTERVENTIONS_CAP, (
            f"{len(room['interventions'])} intervention kaldı; tavan uygulanmadı"
        )
        # en yeniler korunur (en eski düşer)
        assert room["interventions"][-1] == {"i": 599}
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


def test_room_events_dead_store_is_removed():
    """room['events'] hiçbir yerde okunmayan saf birikimdi; katmanlar eklemez.

    Doğrudan _send_event'e de senkron çağrılır (enqueue pump'ı asenkrondur;
    yalnız broadcast_event ile test, mutasyonda yarışa düşer).
    """
    import asyncio
    from agent_core.schemas.telemetry import GenericLogEvent

    api, room = _fresh_room("r1-events")
    try:
        evt = GenericLogEvent(task_id="op_evt_probe", message="m")
        api.broadcast_event("r1-events", evt)
        assert "events" not in room, "broadcast katmanı room['events'] yazıyor"
        # WS pump'unun çalıştırdığı gönderim katmanı: senkron doğrula
        asyncio.run(api._send_event(room, evt))
        assert "events" not in room, "send katmanı ölü room['events'] biriktiriyor"
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


# --------------------------------------------------------------------------
# R3  Identifier uzunluk sınırları (görev kimliği giriş noktaları)
# --------------------------------------------------------------------------
def test_chat_payload_task_id_length_limited():
    from pydantic import ValidationError

    from backend.api import ChatPayload

    with pytest.raises(ValidationError):
        ChatPayload(task_id="a" * 129, target_profile={}, user_profile={}, target_message="x")
    ok = ChatPayload(task_id="a" * 128, target_profile={}, user_profile={}, target_message="x")
    assert ok.task_id == "a" * 128


def test_cancel_halt_reject_oversized_task_id():
    from fastapi.testclient import TestClient

    from backend import api
    api.app.state.rooms.clear()
    try:
        with TestClient(api.app, raise_server_exceptions=False) as client:
            r_long = client.post(f"/api/tasks/{'a' * 200}/cancel")
            assert r_long.status_code == 422, f"200 karakterlik task_id 422 vermedi: {r_long.status_code}"
            r_bad = client.post("/api/tasks/bad*id/cancel")
            assert r_bad.status_code == 400, f"geçersiz task_id biçimi 400 vermedi: {r_bad.status_code}"
            assert r_bad.json()["error"]["code"] == "INVALID_TASK_ID"
            r_halt = client.post(f"/api/tasks/{'a' * 200}/halt")
            assert r_halt.status_code == 422
            # reason uzunluğu da sınırlı
            r_reason = client.post("/api/tasks/op_x/cancel?reason=" + "r" * 501)
            assert r_reason.status_code == 400
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


def test_delete_task_rejects_oversized_task_id():
    from fastapi.testclient import TestClient

    from backend import api
    api.app.state.rooms.clear()
    try:
        with TestClient(api.app, raise_server_exceptions=False) as client:
            r = client.delete(f"/api/tasks/{'a' * 200}?client_id=ci")
            assert r.status_code == 400, f"200 karakterlik task_id 400 vermedi: {r.status_code}"
            assert r.json()["error"]["code"] == "INVALID_TASK_ID"
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


# --------------------------------------------------------------------------
# R4  P1-6 — profil dışı URL'lerde kazıma BAŞLATILMAZ
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "https://www.instagram.com/p/CxYz123Ab/",
    "https://www.instagram.com/reel/DaBc9/",
    "https://www.instagram.com/explore/tags/kedi/",
    "https://www.instagram.com/stories/someone/123/",
    "https://www.instagram.com/accounts/login/",
    "https://www.instagram.com/",
])
def test_scrape_instagram_refuses_non_profile_urls(url):
    from agent_core.scraper.instagram_ghost import InsufficientEvidenceError
    from agent_core.services.platform_registry import scrape_instagram
    import asyncio

    with pytest.raises(InsufficientEvidenceError):
        asyncio.run(scrape_instagram(url))


def test_extract_username_accepts_real_profile():
    from agent_core.services.platform_registry import extract_username

    assert extract_username("https://www.instagram.com/ornek_kullanici/") == "ornek_kullanici"
    assert extract_username("https://www.instagram.com/ornek.kullanici_2?x=1") == "ornek.kullanici_2"
    assert extract_username("@ornek") == ""  # host yok -> çözümleme yok


# --------------------------------------------------------------------------
# R5  P2-9 — bozuk learnings.json: yedek + atomik yazım + 500 YASAK
# --------------------------------------------------------------------------
def test_corrupt_learnings_gets_quarantined_and_recovers(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend import api

    monkeypatch.setenv("PINEAL_MEMORY_PATH", str(tmp_path))
    api.app.state.rooms.clear()
    room = api.get_room("r5-override")
    storage = room["executor"].memory.storage_path
    os.makedirs(storage, exist_ok=True)
    lp = os.path.join(storage, "learnings.json")
    with open(lp, "w", encoding="utf-8") as fh:
        fh.write("{ kesinlikle bozuk")

    try:
        with TestClient(api.app, raise_server_exceptions=False) as client:
            r = client.post(
                "/api/override",
                json={"client_id": "r5-override", "fact": "yeni gercek", "tag": "t"},
            )
        assert r.status_code == 200, f"bozuk learnings.json hâlâ 500 üretiyor: {r.status_code} {r.text[:100]}"
        assert r.json().get("quarantined"), "bozuk dosya yedeklenmedi"

        # yedek var + yeni dosya geçerli JSON ve yeni kayıt içeriyor
        backups = [f for f in os.listdir(storage) if f.startswith("learnings.json.corrupt.")]
        assert backups, "bozuk dosyanın yedeği yok"
        with open(lp, encoding="utf-8") as fh:
            data = json.load(fh)
        assert any(e["fact"] == "yeni gercek" for e in data), "yeni kayıt atomik yazılmamış"
    finally:
        api.app.state.rooms.clear()
        api._rooms_last_seen.clear()


# --------------------------------------------------------------------------
# R6  P1-7 — anti-halüsinasyon kapısı üretim yardımcısında devrede
# --------------------------------------------------------------------------
def test_scrape_confidence_gate_blocks_weak_evidence(monkeypatch):
    from agent_core.scraper.instagram_ghost import InsufficientEvidenceError
    from agent_core.services.platform_registry import check_scrape_confidence

    monkeypatch.setenv("PINEAL_MIN_SCRAPER_CONFIDENCE", "0.6")

    class FakeScraper:
        def __init__(self, score):
            self.score = score

        def evaluate_confidence(self, profile):
            return self.score

    emitted = []
    with pytest.raises(InsufficientEvidenceError):
        check_scrape_confidence(FakeScraper(0.3), object(), lambda lvl, msg: emitted.append(msg))
    assert any("SCRAPER CONFIDENCE: 0.30" in m for m in emitted), "güven skoru telemetriye düşmedi"

    score = check_scrape_confidence(FakeScraper(0.9), object(), lambda lvl, msg: None)
    assert score == 0.9


def test_scrape_confidence_threshold_is_env_driven(monkeypatch):
    from agent_core.services.platform_registry import _min_scrape_confidence

    monkeypatch.setenv("PINEAL_MIN_SCRAPER_CONFIDENCE", "0.4")
    assert _min_scrape_confidence() == 0.4
    monkeypatch.setenv("PINEAL_MIN_SCRAPER_CONFIDENCE", "bozuk")
    assert _min_scrape_confidence() == 0.6
