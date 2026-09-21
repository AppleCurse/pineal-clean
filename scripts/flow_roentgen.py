#!/usr/bin/env python3
"""flow_roentgen.py — uçtan uca akış röntgeni (SALT TEŞHİS, üretim kodu değil).

Ne yapar?
  Gerçek boru hattını (FastAPI -> /api/initiate -> PinealExecutor) koşturur ve
  KODUN NE ÜRETTİĞİ ile UI'YE NE ULAŞTIĞINI yan yana koyar. Hiçbir canlı LLM
  çağrısı yapmaz (gateway stub'lanır), hiçbir üretim dosyasına yazmaz
  (bellek/cache geçici dizine yönlendirilir).

Modlar:
  stub   : Bütün boru hattı, şema-dolduran stub LLM ile koşar. LLM çağrı izi
           (hangi ajan, hangi şema, kaç çağrı) + WS çerçeve envanteri +
           TaskSnapshot alanlarının WS'ye taşınıp taşınmadığı raporlanır.
  ghost  : LLM askıya alınır ve görev timeout'u kısaltılır. Timeout sonrası
           odanın "active_tasks" durumu, terminal olmayan hayalet snapshot'lar
           ve yeni görev kabulünün kilitlenip kilitlenmediği raporlanır.
  all    : ikisi (varsayılan).

Kullanım:
  python scripts/flow_roentgen.py                # tümü, stdout raporu
  python scripts/flow_roentgen.py --mode stub --out /tmp/rontgen.json

Çıkış kodu her zaman 0'dır: bu araç bir KARAR değil, ÖLÇÜM üretir.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
import typing
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# --- İzolasyon: üretim belleğine/cache'ine dokunma, canlı LLM kapalı ---------
_TMP = tempfile.mkdtemp(prefix="flow_roentgen_")
os.environ.setdefault("PINEAL_ENV", "development")
os.environ["PINEAL_CACHE_PATH"] = os.path.join(_TMP, "responses.db")
os.environ["PINEAL_MEMORY_PATH"] = os.path.join(_TMP, "memory")
os.environ["LIVE_LLM_E2E"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from agent_core.services.llm_gateway import LLMGateway  # noqa: E402

# TaskSnapshot üzerinde yaşayıp WS payload'larına taşınması beklenen alanlar.
TASK_SNAPSHOT_FIELDS = (
    "followers", "follower_audit", "timing_forensics", "psychodynamic_depth",
    "depth_report", "visual_evidence", "shadow_profile", "osint_footprint",
    "holistic_profile", "evidence_chain", "frequency_map", "seismos_events",
    "void_map", "strata_map", "gravity_map", "pulse_map", "key_matrix",
    "pillar_bundle",
)

_TARGET_PROFILE = {
    "username": "@rontgen_target",
    "bio": "Mimar. Gece calisirim. Kentsel doku ve analog fotograf.",
    "posts": [
        "Gece yuruyusleri iyi geliyor, kentsel doku nefes aldiriyor",
        "Yeni proje uzerinde geceleri calisiyorum",
        "Sessizlik huzurdur ama kalabalik gurultu yoruyor",
    ],
    "post_times": [
        "2026-01-02T23:10:00+00:00",
        "2026-02-11T02:40:00+00:00",
        "2026-03-05T21:05:00+00:00",
    ],
    "posts_meta": [
        {"like_count": 12, "comment_count": 2},
        {"like_count": 30, "comment_count": 5},
        {"like_count": 8, "comment_count": 1},
    ],
    "post_types": ["image", "reel", "image"],
    "images": [],
    "followers": 1200,
    "following": 300,
    "is_private": False,
}

_INITIATE_BODY = {
    "url": "https://www.instagram.com/rontgen_target/",
    "rituals": "cay,kitap",
    "playlist": "neeset ertas",
    "envies": "derin bag",
}


def _stub_scraper(profile: dict):
    async def _scrape(url, cookie="", log=None):  # imza: platform_registry.scrape_instagram
        if log:
            log("INFO", "RONTGEN: kazima stub (gercek tarayici yok)")
        return dict(profile)

    return _scrape


@contextmanager
def _patched_scraper(profile: dict):
    """Kazımayı stub'lar; canlı Playwright'a hiç dokunulmaz."""
    import backend.api as api
    import agent_core.services.platform_registry as registry

    stub = _stub_scraper(profile)
    original = registry.scrape_instagram
    registry.scrape_instagram = stub
    api.scrape_instagram = stub
    try:
        yield
    finally:
        registry.scrape_instagram = original


def _fill_schema(model, depth: int = 0):
    """Şema-dolduran stub: model alanlarını kanıt taşıyan örnek değerlerle doldurur.

    Gerçek LLM'in yerine geçmez; yalnız "boru hattı bu şemayla ne yapıyor"
    sorusunu ölçmek için deterministik dolgu üretir.
    """
    if depth > 6:
        return None
    kwargs: dict = {}
    for name, field in model.model_fields.items():
        ann = field.annotation
        origin = typing.get_origin(ann)
        if origin in (list, typing.List, typing.Sequence):
            inner = typing.get_args(ann)[0]
            if isinstance(inner, type) and hasattr(inner, "model_fields"):
                kwargs[name] = [_fill_schema(inner, depth + 1)]
            else:
                kwargs[name] = ["Rontgen kaniti: gece uretkenligi ve kentsel doku tekrar ediyor"]
            continue
        if origin in (typing.Union,):
            args = [a for a in typing.get_args(ann) if a is not type(None)]
            ann = args[0] if args else str
            origin = typing.get_origin(ann)
            if origin in (list, typing.List, typing.Sequence):
                inner = typing.get_args(ann)[0]
                if isinstance(inner, type) and hasattr(inner, "model_fields"):
                    kwargs[name] = [_fill_schema(inner, depth + 1)]
                else:
                    kwargs[name] = ["Rontgen kaniti: hedef ritmi tekrar ediyor"]
                continue
        if isinstance(ann, type) and hasattr(ann, "model_fields"):
            kwargs[name] = _fill_schema(ann, depth + 1)
        elif ann is float:
            kwargs[name] = 0.9
        elif ann is int:
            kwargs[name] = 3
        elif ann is bool:
            kwargs[name] = True
        elif ann is str:
            kwargs[name] = (
                "Rontgen kanit metni: hedef gece saatlerinde uretiyor ve "
                "kentsel dokuyu tekrar ediyor"
            )
        else:
            kwargs[name] = None
    try:
        return model.model_validate(kwargs)
    except Exception:
        return model.model_construct(**kwargs)


@contextmanager
def _stub_llm(trace: list | None = None, hang_seconds: float = 0.0):
    """Gateway'i stub'lar. hang_seconds > 0 ise çağrılar askıda bırakılır.

    Stub, GERÇEK gateway'in aktivite sözleşmesini taklit eder: eğer bir
    `capture_calls` kapsamı açıksa kaydı o kapsama yazar (`agent_id` ile). Böylece
    "hangi ajan hangi çağrıyı yaptı" sorusu stub modunda da doğru yanıtlanır —
    aksi hâlde kapsam içindeki çağrılar (ör. authentic vector) görünmez kalır.
    """
    from agent_core.services.llm_gateway import _active_call_scope

    log = trace if trace is not None else []
    originals = {name: getattr(LLMGateway, name) for name in ("query", "query_json", "query_json_chain")}

    def _record(fn_name: str, schema, kwargs) -> dict:
        scope = _active_call_scope.get()
        entry = {
            "fn": fn_name,
            "schema": getattr(schema, "__name__", None),
            "agent": kwargs.get("agent_name") or (getattr(scope, "agent_id", None) if scope else None),
            "task": kwargs.get("task") or (getattr(scope, "task_id", None) if scope else None),
        }
        log.append(entry)
        if scope is not None and hasattr(scope, "records"):
            scope.records.append({
                "call_id": str(uuid.uuid4()),
                "kind": fn_name,
                "model": "stub",
                "provider": "stub",
                "agent_id": getattr(scope, "agent_id", None),
                "task_id": getattr(scope, "task_id", None),
            })
        return entry

    async def _query(self, prompt, *a, **k):
        _record("query", None, k)
        if hang_seconds:
            await asyncio.sleep(hang_seconds)
        return "Rontgen dogrulama notu: iddia veriyle uyumlu."

    async def _query_json(self, prompt, schema=None, *a, **k):
        _record("query_json", schema, k)
        if hang_seconds:
            await asyncio.sleep(hang_seconds)
        return _fill_schema(schema) if schema is not None else {}

    async def _query_json_chain(self, prompt, schema=None, *a, **k):
        _record("query_json_chain", schema, k)
        if hang_seconds:
            await asyncio.sleep(hang_seconds)
        return _fill_schema(schema) if schema is not None else {}

    LLMGateway.query = _query
    LLMGateway.query_json = _query_json
    LLMGateway.query_json_chain = _query_json_chain
    try:
        yield log
    finally:
        for name, fn in originals.items():
            setattr(LLMGateway, name, fn)


@contextmanager
def _watch_upstream(records: list):
    """`upstream_findings_block` çağrılarını sayar (hangi ajan gördü, kaç bulgu).

    Tüketiciler bloğu ``from … import upstream_findings_block`` ile kendi
    modül ad alanına bağlar; bu yüzden TÜKETİCİ modülünü yamalarız, kaynağı değil.
    """
    # [BOSS-9] Tüketici listesi genişletildi: kör kalan LLM ajanları da artık
    # blok alıyor; hangisinin gerçekten okuduğu burada ölçülür.
    import agent_core.agents.authenticity_auditor as authenticity
    import agent_core.agents.depth_analyst as depth
    import agent_core.agents.human_behavior as behavior
    import agent_core.agents.mirror_truth as mirror
    import agent_core.agents.pattern_interrupt as pattern
    import agent_core.agents.resonance_synthesizer as synth
    import agent_core.agents.target_psyche_profiler as profiler

    def _wrap(module, label):
        original = module.upstream_findings_block

        def _recorder(payload):
            findings = payload.get("_upstream_findings") if isinstance(payload, dict) else None
            block = original(payload)
            records.append({
                "consumer": label,
                "findings_count": len(findings) if isinstance(findings, list) else 0,
                "block_chars": len(block or ""),
                "agents_seen": sorted({f.get("agent") for f in findings or []}),
            })
            return block

        module.upstream_findings_block = _recorder
        return original

    watched = [
        (profiler, "target_psyche_profiler"),
        (synth, "resonance_synthesizer"),
        (mirror, "mirror_truth"),
        (behavior, "human_behavior"),
        (pattern, "pattern_interrupt"),
        (depth, "depth_analyst"),
        (authenticity, "authenticity_auditor"),
    ]
    originals = [(module, _wrap(module, label)) for module, label in watched]
    try:
        yield records
    finally:
        for module, original in originals:
            module.upstream_findings_block = original


def _drain_ws(ws, *, limit: int = 400, stop_on_result: bool = True, budget_s: float = 30.0):
    frames: list = []
    deadline = time.time() + budget_s
    while len(frames) < limit and time.time() < deadline:
        try:
            frame = ws.receive_json()
        except Exception:
            break
        frames.append(frame)
        kind = frame.get("type") or (frame.get("event") or {}).get("event_type")
        if stop_on_result and kind == "result":
            break
    return frames


def run_stub_mode() -> dict:
    from backend.api import app

    trace: list = []
    upstream_calls: list = []
    client_id = "rontgen_stub_" + uuid.uuid4().hex[:6]
    with _patched_scraper(_TARGET_PROFILE), _stub_llm(trace), _watch_upstream(upstream_calls):
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/{client_id}") as ws:
                t0 = time.time()
                response = client.post(
                    "/api/initiate",
                    json={"client_id": client_id, **_INITIATE_BODY},
                )
                body = response.json() if response.status_code == 200 else {"error": response.text}
                frames = _drain_ws(ws) if response.status_code == 200 else []
                wall_s = round(time.time() - t0, 3)
            room = app.state.rooms.get(client_id) or {}

    result = next((f for f in frames if f.get("type") == "result"), None) or {}
    snapshots = [f for f in frames if f.get("type") == "snapshot_update"]
    runs = result.get("runs") or {}

    return {
        "mode": "stub",
        "initiate_status": response.status_code,
        "initiate_body": body,
        "wall_seconds": wall_s,
        "frame_count": len(frames),
        "frame_types": [(f.get("type") or (f.get("event") or {}).get("event_type")) for f in frames],
        "final_status": result.get("status"),
        "llm_calls_total": len(trace),
        "llm_calls": trace,
        "llm_calls_by_agent": _count_by(trace, "agent"),
        "llm_calls_by_schema": _count_by(trace, "schema"),
        "upstream_block_calls": upstream_calls,
        "run_errors": {
            name: run.get("error_message") for name, run in runs.items()
            if run.get("error_message")
        },
        "planned_agents": result.get("planned_agents") or [],
        "runs": {
            name: {
                "status": run.get("status"),
                "model": run.get("model"),
                "via": run.get("via"),
                "run_source": run.get("run_source"),
                "confidence": run.get("confidence"),
            }
            for name, run in runs.items()
        },
        "run_call_ids": {name: len(run.get("call_ids") or []) for name, run in runs.items()},
        "snapshot_field_gap": {
            field: {
                "in_snapshot": field in {
                    k for snap in snapshots for k in snap.keys()
                },
                "in_result": field in result,
            }
            for field in TASK_SNAPSHOT_FIELDS
        },
        "evidence_chain_agents": [e.get("agent") for e in (result.get("evidence_chain") or [])],
        "sealed_memory_files": sorted(os.listdir(os.environ["PINEAL_MEMORY_PATH"]))
        if os.path.isdir(os.environ["PINEAL_MEMORY_PATH"]) else [],
        "room_active_tasks": list((room.get("active_tasks") or {}).keys()),
    }


def _count_by(rows: list, key: str) -> dict:
    counts: dict = {}
    for row in rows:
        name = row.get(key)
        counts[str(name)] = counts.get(str(name), 0) + 1
    return counts


def run_ghost_mode() -> dict:
    """Timeout sonrası oda durumu: hayalet snapshot ve 503 kilidi var mı?"""
    os.environ["PINEAL_TASK_TIMEOUT_SECONDS"] = "3"
    os.environ["PINEAL_TASK_MAX_ATTEMPTS"] = "1"
    os.environ["PINEAL_ROOM_ACTIVE_TASKS_CAP"] = "2"

    import backend.api as api

    # DİKKAT: _ROOM_ACTIVE_TASKS_CAP modül import'unda bağlanır (env o an okunur).
    # stub modu backend.api'yi zaten import etmiş olabilir; bu yüzden hem env hem
    # modül sabiti ayarlanır ve raporda ETKİN değer yazılır.
    effective_cap = 2
    api._ROOM_ACTIVE_TASKS_CAP = effective_cap

    client_id = "rontgen_ghost_" + uuid.uuid4().hex[:6]
    attempts: list = []
    with _patched_scraper(_TARGET_PROFILE), _stub_llm(hang_seconds=120):
        with TestClient(api.app) as client:
            tid = None
            for index in range(3):
                response = client.post(
                    "/api/initiate",
                    json={"client_id": client_id, **_INITIATE_BODY},
                )
                entry = {"attempt": index + 1, "status_code": response.status_code}
                if response.status_code == 200:
                    entry["task_id"] = response.json().get("task_id")
                    if index == 0:
                        tid = entry["task_id"]
                        with client.websocket_connect(f"/ws/{client_id}") as ws:
                            entry["frames"] = _drain_ws(ws)
                else:
                    entry["body"] = response.text[:200]
                attempts.append(entry)
                time.sleep(4)

            room = api.app.state.rooms.get(client_id) or {}
            states = {
                key: str(getattr(getattr(snap, "status", None), "value",
                                 getattr(snap, "status", None)))
                for key, snap in (room.get("active_tasks") or {}).items()
            }
            full_before = api._active_tasks_full(room)
            room["_stale_prune_ts"] = 0.0
            api._prune_room_stale_state(room)
            states_after_sweep = {
                key: str(getattr(getattr(snap, "status", None), "value",
                                 getattr(snap, "status", None)))
                for key, snap in (room.get("active_tasks") or {}).items()
            }
            full_after = api._active_tasks_full(room)
            cleanup = None
            if tid:
                deleted = client.delete(f"/api/tasks/{tid}?client_id={client_id}")
                cleanup = {"delete_status": deleted.status_code,
                           "remaining": list((room.get("active_tasks") or {}).keys())}

    return {
        "mode": "ghost",
        "task_timeout_seconds": 3,
        "active_tasks_cap": effective_cap,
        "active_tasks_cap_effective": api._ROOM_ACTIVE_TASKS_CAP,
        "initiate_attempts": attempts,
        "active_tasks_states": states,
        "active_tasks_states_after_retention_sweep": states_after_sweep,
        "active_tasks_full_before_sweep": full_before,
        "active_tasks_full_after_sweep": full_after,
        "ghost_task_ids": [k for k, v in states.items() if v not in api._TERMINAL_PIPELINE_STATES],
        "manual_cleanup": cleanup,
    }


def _print_stub(report: dict) -> None:
    print("=" * 72)
    print("MOD: stub — tüm boru hattı, canlı LLM YOK")
    print("=" * 72)
    print(f"/api/initiate        : {report['initiate_status']}  {report['initiate_body']}")
    print(f"duvar saati          : {report['wall_seconds']}s | WS çerçeve: {report['frame_count']}")
    print(f"nihai durum          : {report['final_status']}")
    print(f"LLM çağrısı (stub)   : {report['llm_calls_total']}")
    print(f"  ajan bazında       : {json.dumps(report['llm_calls_by_agent'], ensure_ascii=False)}")
    print(f"  şema bazında       : {json.dumps(report['llm_calls_by_schema'], ensure_ascii=False)}")
    print("\nAjan koşuları (UI'ye giden 'runs'):")
    for name, run in report["runs"].items():
        print(f"  {name:24s} {str(run['status']):10s} model={run['model']} via={run['via']} src={run['run_source']}")
    print("\nTaskSnapshot alanı -> WS'ye taşındı mı?")
    for field, where in report["snapshot_field_gap"].items():
        mark = "OK " if (where["in_snapshot"] or where["in_result"]) else "YOK"
        print(f"  [{mark}] {field:22s} snapshot={where['in_snapshot']} result={where['in_result']}")
    print(f"\nMühürlenen bellek dosyaları: {report['sealed_memory_files']}")
    print(f"Kanıt zinciri ajanları: {report['evidence_chain_agents']}")
    print("\nUpstream bulgu bloğu tüketicileri (kör kalan ajanlar burada görünmez):")
    seen = {}
    for call in report.get("upstream_block_calls") or []:
        key = call["consumer"]
        seen.setdefault(key, []).append(call)
    for consumer, calls in seen.items():
        nonempty = [c for c in calls if c["findings_count"]]
        print(f"  {consumer:24s} toplam={len(calls)} dolu={len(nonempty)} "
              f"son_bulgu_sayısı={calls[-1]['findings_count']}")
    if not seen:
        print("  (hiç çağrılmadı)")
    print(f"\nAjan hata mesajları: {json.dumps(report.get('run_errors') or {}, ensure_ascii=False)}")


def _print_ghost(report: dict) -> None:
    print()
    print("=" * 72)
    print("MOD: ghost — görev timeout'u sonrası oda durumu")
    print("=" * 72)
    for entry in report["initiate_attempts"]:
        print(f"  initiate #{entry['attempt']}: HTTP {entry['status_code']} "
              f"{entry.get('task_id', entry.get('body', ''))}")
    print(f"  active_tasks (tavan {report['active_tasks_cap']}): "
          f"{json.dumps(report['active_tasks_states'], ensure_ascii=False)}")
    print(f"  retention sweep sonrası: "
          f"{json.dumps(report['active_tasks_states_after_retention_sweep'], ensure_ascii=False)}")
    print(f"  hayalet (terminal olmayan) görevler: {report['ghost_task_ids']}")
    print(f"  oda 'dolu' mu: sweep öncesi={report['active_tasks_full_before_sweep']} "
          f"sonrası={report['active_tasks_full_after_sweep']}")
    print(f"  elle temizlik (DELETE): {report['manual_cleanup']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pineal uçtan uca akış röntgeni")
    parser.add_argument("--mode", choices=("stub", "ghost", "all"), default="all")
    parser.add_argument("--out", default="", help="JSON rapor yolu (boşsa yazılmaz)")
    args = parser.parse_args()

    report: dict = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC",
                    "temp_dir": _TMP}
    if args.mode in ("stub", "all"):
        report["stub"] = run_stub_mode()
        _print_stub(report["stub"])
    if args.mode in ("ghost", "all"):
        report["ghost"] = run_ghost_mode()
        _print_ghost(report["ghost"])

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON rapor: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
