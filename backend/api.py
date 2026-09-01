from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import asyncio
import json
import logging
import os
import hashlib
import time

logger = logging.getLogger("backend.api")
from datetime import datetime
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from agent_core.aspasia.aspasia_chief import AspasiaChief
from agent_core.chat.dialogue_manager import DialogueManager
from agent_core.scraper.instagram_ghost import InstagramGhostScraper
from agent_core.services import crawl_enricher, socid_enricher
from agent_core.services.dependency_health import (
    StartupDependencyError,
    check_startup_dependencies,
)
from agent_core.schemas.telemetry import ErrorHaltEvent, Severity, TaskCancelledEvent
from agent_core.services.runtime_status import rust_core_status
from agent_core.services.task_lifecycle import TaskLifecycleRegistry
from agent_core.shadow.shadow_executor import ShadowExecutor
from agent_core.utils.security import (
    SecurityConfigurationError,
    redact_structure,
    redact_text,
    safe_child_path,
    security_posture,
    token_matches,
    validate_identifier,
)
from agent_core.task_executor import PinealExecutor, InsufficientEvidenceError


shadow_executor = ShadowExecutor()
dialogue_manager = DialogueManager()
aspasia_chief = AspasiaChief()

@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        startup_health = check_startup_dependencies()
        startup_health["security"] = security_posture()
        startup_health["components"] = {"rust_core": rust_core_status()}
        application.state.startup_health = startup_health
    except (StartupDependencyError, SecurityConfigurationError) as exc:
        application.state.startup_health = exc.as_dict()
        logger.critical("Startup security/dependency gate failed: %s", exc.error_code)
        raise

    yield
    # Kapanista oda gonderici task'lerini iptal et (temiz kapanis)
    for room in application.state.rooms.values():
        task = room.get("sender_task")
        if task and not task.done():
            task.cancel()
        for mission in room.get("mission_tasks", {}).values():
            if not mission.done():
                mission.cancel()
    application.state.rooms.clear()

app = FastAPI(title="PINEAL-HERETIC v2.0 API", lifespan=lifespan)
app.state.startup_health = {
    "status": "starting",
    "error_code": None,
    "dependencies": [],
    "components": {"rust_core": rust_core_status()},
}


@app.get("/health")
async def health():
    health_status = app.state.startup_health
    if health_status.get("status") != "ready":
        return JSONResponse(health_status, status_code=503)
    return health_status


# --- CORS (FAZ 3): ayni-origin serviste CORS gereksizdir; disaridan erisim
# istenirse PINEAL_ALLOWED_ORIGINS ile acilir. Varsayilan yalnizca localhost. ---
_default_origins = [
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:5173", "http://127.0.0.1:5173",
]
_allowed = os.getenv("PINEAL_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _allowed.split(",") if o.strip() and o.strip() != "*"] or _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# --- Auth (FAZ 3): PINEAL_TOKEN tanimliysa tum /api/* X-API-Key ister;
# tanimli degilse sistem acik calisir (yerel tek kullanicili arac, geriye uyumluluk). ---
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        try:
            posture = security_posture()
        except SecurityConfigurationError as exc:
            return JSONResponse(
                {"error": {"code": exc.error_code, "message": "Secure startup configuration required"}},
                status_code=503,
            )
        if posture["auth_required"] and not token_matches(request.headers.get("x-api-key")):
            return JSONResponse(
                {"error": {"code": "UNAUTHORIZED", "message": "X-API-Key gerekli veya hatalı"}},
                status_code=401,
            )
        if request.url.path.startswith("/api/experimental/"):
            identity = request.headers.get("x-api-key") or (request.client.host if request.client else "unknown")
            identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
            if not rate_limit(f"experimental:{identity_hash}", "experimental"):
                return JSONResponse(
                    {"error": {"code": "RATE_LIMITED", "message": "Experimental endpoint rate limit exceeded"}},
                    status_code=429,
                )
    return await call_next(request)

# --- Tutarli hata modeli (FAZ 3) ---
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        {"error": {"code": str(exc.status_code), "message": str(exc.detail)}},
        status_code=exc.status_code,
    )

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        {"error": {"code": "INTERNAL", "message": type(exc).__name__}},
        status_code=500,
    )

# --- Basit kayan-pencere rate limit (FAZ 3; ek bagimlilik yok) ---
RATE_LIMITS = {
    "initiate": (5, 60),
    "aspasia": (20, 60),
    "experimental": (10, 60),
}  # (request count, window seconds)
_rate_buckets: Dict[str, deque] = defaultdict(deque)


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def rate_limit(key: str, bucket: str) -> bool:
    """True = izin ver; False = limit asildi (429)."""
    limit, window = RATE_LIMITS.get(bucket, (999, 1))
    now = time.monotonic()
    q = _rate_buckets[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True

app.state.rooms = {}  # client_id -> {"executor": PinealExecutor, "vault": {}, "websockets": set()}

# W5: tarayici yetenegi probu (60sn cache). Telemetri artik import basarisi
# degil, GERCEK capability raporlar (x_scraper / instagram_scraper / browser_installed).
_telemetry_capability = {"ts": 0.0, "value": None}
_telemetry_capability_lock = asyncio.Lock()

async def _scraper_capability() -> dict:
    now = time.monotonic()
    cached = _telemetry_capability["value"]
    if cached is not None and now - _telemetry_capability["ts"] < 60.0:
        return cached
    async with _telemetry_capability_lock:
        cached = _telemetry_capability["value"]
        if cached is not None and time.monotonic() - _telemetry_capability["ts"] < 60.0:
            return cached
        result = {"instagram": False, "browser": False}
        try:
            if InstagramGhostScraper is not None:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    exe = p.chromium.executable_path
                    result["browser"] = bool(exe and os.path.exists(exe))
                    result["instagram"] = result["browser"]
        except Exception:
            result = {"instagram": False, "browser": False}
        _telemetry_capability["ts"] = time.monotonic()
        _telemetry_capability["value"] = result
        return result

def get_room(client_id: str) -> dict:
    if client_id not in app.state.rooms:
        executor = PinealExecutor(
            log_callback=lambda lvl, msg: sync_log(client_id, lvl, msg),
            emit_event_callback=lambda evt: sync_event(client_id, evt),
            snapshot_callback=lambda s: sync_snapshot(client_id, s)
        )
        vault = {}
        
        # Otomatik Kasa (.pineal_vault.json / .env) yüklemesi
        vault_file = ".pineal_vault.json"
        if os.path.exists(vault_file):
            try:
                with open(vault_file, "r", encoding="utf-8") as f:
                    vault = json.load(f)
            except Exception:
                pass

        api_key = vault.pop("api_key", None) or os.getenv("OPENROUTER_API_KEY")
        if api_key and not api_key.startswith("sk-or-v1-YOUR"):
            executor.llm_gateway.set_key(api_key)
            if shadow_executor is not None:
                shadow_executor.llm_gateway.set_key(api_key)
            if dialogue_manager is not None:
                dialogue_manager.llm.set_key(api_key)
            vault["or_key"] = True

        tavily = vault.get("tavily_key") or os.getenv("TAVILY_API_KEY")
        # [FIX] .env.example/SearchEngine "SERPAPI_API_KEY" kullanır; eski
        # "SERPAPI_KEY" yalnızca geriye uyumluluk için ikincil okunur.
        serpapi = vault.get("serpapi_key") or os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
        exa = vault.get("exa_key") or os.getenv("EXA_API_KEY")
        if tavily or serpapi or exa:
            executor.search_engine.set_keys(tavily=tavily, serpapi=serpapi, exa=exa)
            vault["search_keys"] = True
        # Vault explicit value wins; otherwise honour USE_LOCAL_LLM env
        # (do not treat missing key as False when env says true).
        if "use_local" in vault:
            use_local = bool(vault.get("use_local"))
        else:
            use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        executor.llm_gateway.use_local = use_local

        app.state.rooms[client_id] = {
            "executor": executor,
            "vault": vault,
            "websockets": set(),
            "logs": [],
            "aspasia": AspasiaChief(llm_gateway=executor.llm_gateway) if AspasiaChief else None,
            "queue": asyncio.Queue(maxsize=2000),
            "sender_task": None,
            "mission_tasks": {},
            "lifecycle": TaskLifecycleRegistry(),
            "telemetry_delivery": {
                "state": "NORMAL",
                "dropped_messages_total": 0,
                "dropped_event_count": 0,
                "dropped_by_kind": {},
            },
        }
        # FIFO gonderici: tum log/event/snapshot/result mesajlari sirayla iletilir.
        try:
            loop = asyncio.get_running_loop()
            app.state.rooms[client_id]["sender_task"] = loop.create_task(
                _room_sender(app.state.rooms[client_id])
            )
        except RuntimeError:
            pass
    return app.state.rooms[client_id]

def get_executor(client_id: str) -> PinealExecutor:
    return get_room(client_id)["executor"]

def get_vault(client_id: str) -> dict:
    return get_room(client_id)["vault"]


# ---------------------------------------------------------------
# TELEMETRI BUS — oda basina FIFO kuyruk (ADIM 3)
# Oncesi: sync_* -> loop.create_task(...) deseninde eventler 'result'
# mesajiyla yarisiyor, ilk canli testte hic event ulasmiyordu.
# Simdi: her mesaj kuyruga girer, tek gonderici SIRAYLA iletir.
# ---------------------------------------------------------------

async def _room_sender(room: dict):
    queue: asyncio.Queue = room["queue"]
    while True:
        kind, payload = await queue.get()
        try:
            if kind == "log":
                await _send_log(room, payload)
            elif kind == "event":
                await _send_event(room, payload)
            elif kind == "snapshot":
                await _send_snapshot(room, payload)
            elif kind == "result":
                await _send_result(room, payload)
            elif kind == "result_error":
                await _send_result_error(room, payload)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # gonderici task asla olmemeli
            print(f"[room_sender] hata: {type(e).__name__}: {e}")

def _lifecycle(room: dict) -> TaskLifecycleRegistry:
    return room.setdefault("lifecycle", TaskLifecycleRegistry())


def _delivery_status(room: dict) -> dict:
    delivery = room.setdefault("telemetry_delivery", {
        "state": "NORMAL",
        "dropped_messages_total": 0,
        "dropped_event_count": 0,
        "dropped_by_kind": {},
    })
    return {
        "state": delivery["state"],
        "dropped_messages_total": delivery["dropped_messages_total"],
        "dropped_event_count": delivery["dropped_event_count"],
        "dropped_by_kind": dict(delivery["dropped_by_kind"]),
    }


def _record_queue_drop(room: dict, kind: str) -> None:
    _delivery_status(room)
    delivery = room["telemetry_delivery"]
    delivery["state"] = "DEGRADED_QUEUE_OVERFLOW"
    delivery["dropped_messages_total"] += 1
    delivery["dropped_by_kind"][kind] = delivery["dropped_by_kind"].get(kind, 0) + 1
    if kind == "event":
        delivery["dropped_event_count"] += 1


def _enqueue(client_id: str, item: tuple):
    if client_id in app.state.rooms:
        room = app.state.rooms[client_id]
        q: asyncio.Queue = room["queue"]
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            try:
                dropped_kind, _ = q.get_nowait()  # Explicit drop-oldest policy.
                _record_queue_drop(room, dropped_kind)
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                # Defensive accounting if another producer fills the slot.
                _record_queue_drop(room, item[0])

async def _send_ws(room: dict, payload: str):
    ws_set = room["websockets"]
    for ws in list(ws_set):
        try:
            await ws.send_text(payload)
        except Exception:
            ws_set.discard(ws)

async def _send_log(room: dict, payload: tuple):
    level, msg = payload
    ts = datetime.now().strftime("%H:%M:%S")
    if "logs" not in room: room["logs"] = []
    room["logs"].append(f"[{ts}] [{level}] {msg}")
    if len(room["logs"]) > 50: room["logs"].pop(0)
    await _send_ws(room, json.dumps({"type": "log", "ts": ts, "level": level, "msg": msg}))

def broadcast_log(client_id: str, level: str, msg: str):
    _enqueue(client_id, ("log", (level, redact_text(msg))))

def sync_log(client_id: str, level: str, msg: str):
    broadcast_log(client_id, level, msg)

async def _send_event(room: dict, telemetry: Any):
    delivery = _delivery_status(room)
    telemetry = telemetry.model_copy(update={
        "delivery_state": delivery["state"],
        "dropped_event_count": delivery["dropped_event_count"],
    })
    if "events" not in room:
        room["events"] = []
    room["events"].append(telemetry)
    await _send_ws(room, telemetry.model_dump_json())


def broadcast_event(client_id: str, event: Any):
    room = app.state.rooms.get(client_id)
    if room is None:
        return
    if hasattr(event, "model_dump"):
        clean_event_data = redact_structure(event.model_dump(mode="json"))
        event = type(event).model_validate(clean_event_data)
    decision = _lifecycle(room).record_event(event)
    if decision.accepted:
        _enqueue(client_id, ("event", decision.envelope))

def sync_event(client_id: str, event: Any):
    broadcast_event(client_id, event)

async def _send_snapshot(room: dict, snapshot: Any):
    def _dump_field(val):
        if val is None:
            return None
        if hasattr(val, "model_dump"):
            return val.model_dump(mode="json")
        return val

    snapshot_telemetry = dict(getattr(snapshot, "telemetry", None) or {})
    snapshot_telemetry["delivery"] = _delivery_status(room)
    snapshot_telemetry["lifecycle"] = _lifecycle(room).metrics()

    payload = json.dumps({
        "type": "snapshot_update",
        "task_id": snapshot.task_id,
        "current_agent": snapshot.current_agent,
        "status": snapshot.status,
        "planned_agents": snapshot.planned_agents,
        "completed_agents": snapshot.completed_agents,
        "halted_reason": getattr(snapshot, "halted_reason", None),
        "resonance_score": getattr(snapshot, "resonance_score", None),
        "holistic_profile": _dump_field(getattr(snapshot, "holistic_profile", None)),
        "follower_audit": _dump_field(getattr(snapshot, "follower_audit", None)),
        "timing_forensics": _dump_field(getattr(snapshot, "timing_forensics", None)),
        "depth_report": _dump_field(getattr(snapshot, "depth_report", None)),
        "visual_evidence": _dump_field(getattr(snapshot, "visual_evidence", None)),
        "shadow_profile": _dump_field(getattr(snapshot, "shadow_profile", None)),
        "osint_footprint": _dump_field(getattr(snapshot, "osint_footprint", None)),
        "telemetry": snapshot_telemetry,
        "runs": {
            name: {
                "status": getattr(r, "status", None),
                "confidence": getattr(r, "confidence", None),
                "started_at": r.started_at.isoformat() if getattr(r, "started_at", None) else None,
                "completed_at": r.completed_at.isoformat() if getattr(r, "completed_at", None) else None,
                "error_message": getattr(r, "error_message", None),
                "call_ids": list(getattr(r, "call_ids", []) or []),
                "output_summary": redact_structure(
                    getattr(r, "output_summary", None) or {}
                ),
                "provenance": redact_structure(
                    (getattr(r, "output_summary", None) or {}).get("_provenance")
                ),
            }
            for name, r in snapshot.agent_runs.items()
        }
    })
    if "active_tasks" not in room:
        room["active_tasks"] = {}
    room["active_tasks"][snapshot.task_id] = snapshot
    await _send_ws(room, payload)

def broadcast_snapshot(client_id: str, snapshot: Any):
    room = app.state.rooms.get(client_id)
    if room is None:
        return
    decision = _lifecycle(room).accept_snapshot(snapshot)
    if decision.accepted:
        _enqueue(client_id, ("snapshot", snapshot))

def sync_snapshot(client_id: str, snapshot: Any):
    broadcast_snapshot(client_id, snapshot)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    try:
        posture = security_posture()
    except SecurityConfigurationError:
        await websocket.close(code=1013)
        return

    await websocket.accept()
    if posture["auth_required"]:
        try:
            auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        except (asyncio.TimeoutError, ValueError):
            await websocket.close(code=1008)
            return
        if auth_message.get("type") != "auth" or not token_matches(auth_message.get("token")):
            await websocket.close(code=1008)
            return
        await websocket.send_json({"type": "auth_ok"})

    room = get_room(client_id)
    room["websockets"].add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        room["websockets"].discard(websocket)

class InitiatePayload(BaseModel):
    client_id: str
    url: str
    rituals: str
    playlist: str
    envies: str
    scraper_type: str = "instagram"
    # [037] fix: aggressiveness/evidence_th kabul ediliyordu ama HİÇBİR davranışa
    # bağlanmamıştı (ölü API sözleşmesi). Kaldırıldı; eşik ayarı gerekiyorsa
    # DecisionConfig üzerinden gerçek davranışla bağlanmalı. Eski istemcilerin
    # bu alanları göndermesi pydantic tarafından sessizce yok sayılır.

# [W4.2] Tek sahiplik: platform kararları agent_core/services/platform_registry'de.
# Rust TaskManager (scripts/run_task.py) aynı registry'yi kullanır; ikinci bir
# karar katmanı YARATILMAZ ([009] duplication dersi). Geriye uyumluluk için
# isimler burada da geçerli.
from agent_core.services.platform_registry import (
    effective_scraper_type as _effective_scraper_type,
    scrape_instagram,
)
# Geriye uyumluluk re-export'u: Dalga 1 sözleşme testleri bu adı backend.api'den
# içe aktarıyor ([024]/[025]/[026] mapping testleri).
from agent_core.services.platform_registry import (  # noqa: F401
    ig_target_profile_update as _ig_target_profile_update,
)


def _new_task_id() -> str:
    """[029] fix: saniye-çözünürlüklü op_HHMMSS çakışıyordu; aynı saniyede iki
    görev (farklı client'lar dahil) aynı memory dosyasında birleşiyordu.
    Tarihi saniye + uuid4 öneki -> CanonicalMemory task_id regex'i ile uyumlu."""
    import uuid
    return f"op_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


async def run_mission(req: InitiatePayload, task_id: Optional[str] = None):
    client_id = req.client_id
    executor = get_executor(client_id)
    vault = get_vault(client_id)
    
    try:
        # [009] Kullanıcı göndermediyse ASLA örnek/placeholder ritüel ÜRETME.
        # Boş kullanıcı verisi -> boş listeler; MirrorOfTruth "user_data_missing"
        # fallback'iyle çalışır. Sahte ritüel ile kullanıcı frekansı kirletilmez.
        user_rituals = [r.strip() for r in req.rituals.split(",") if r.strip()] if req.rituals else []
        user_playlist = [req.playlist.strip()] if req.playlist and req.playlist.strip() else []
        user_envies = [e.strip() for e in req.envies.split(",") if e.strip()] if req.envies else []

        payload = {
            "user_profile": {
                "private_rituals": user_rituals,
                "late_night_playlist": user_playlist,
                "secret_envies": user_envies,
            },
            "user_context": {
                "rituals": ", ".join(user_rituals),
                "playlist": ", ".join(user_playlist),
                "envies": ", ".join(user_envies),
            },
            "target_profile": {"bio": "", "posts": [], "post_times": [], "images": []}
        }
        
        # Otonom Cookie Rotasyonu
        cookie = ""
        cookie_pool = vault.get("x_cookie", "").strip()
        if cookie_pool:
            cookie_list = [c.strip() for c in cookie_pool.split('\n') if c.strip()]
            if cookie_list:
                import random
                cookie = random.choice(cookie_list)
                broadcast_log(client_id, "INFO", "DAEMON: Rotasyondan rastgele cookie seçildi.")
                
        effective_type = _effective_scraper_type(req.url, req.scraper_type)
        if effective_type == "x":
            # Never run Pineal on an empty X profile. Preserve the request and
            # ask the user to authorize a distinct, auditable alternative.
            room = get_room(client_id)
            room["pending_alternative_authorization"] = {
                "url": req.url,
                "requested_at": datetime.now().isoformat(),
                "alternatives": ["public_web_search"],
            }
            broadcast_log(client_id, "WARNING", "X (TWITTER) KAZIMASI DESTEKLENMİYOR: alternatif public-web araştırması için yetki bekleniyor; analiz başlatılmadı.")
            broadcast_result_error(client_id, "awaiting_authorization", "X desteklenmiyor. Aspasia alternatif public-web araştırması için onay bekliyor.")
            return
        if req.url and effective_type == "unsupported_web":
            # [023] fix: tanınmayan platformda URL segmentini Instagram adı gibi
            # kullanıp yanlış hedefi kazımak YASAK. Tahmin üretme, açıkça dur.
            broadcast_log(
                client_id, "WARNING",
                f"PLATFORM DESTEKLENMİYOR: {req.url} — yalnızca Instagram kazıması var; "
                "tanınmayan URL tahmine dayalı kazınmaz, analiz başlatılmadı.",
            )
            broadcast_result_error(
                client_id, "unsupported_platform",
                "Bu URL'nin platformu desteklenmiyor (destekli: Instagram). Analiz başlatılmadı.",
            )
            return
        if req.url and effective_type == "instagram":
            broadcast_log(client_id, "INFO", f"UPLINK: Hedefe sızılıyor -> {req.url} [INSTAGRAM]")
            try:
                # [W4.2] Kazıma tek sahiplikli platform_registry'de; Rust
                # TaskManager (run_task.py) da aynı fonksiyonu kullanır.
                payload["target_profile"].update(await scrape_instagram(
                    req.url, cookie,
                    log=lambda lvl, msg: broadcast_log(client_id, lvl, msg),
                ))
                broadcast_log(client_id, "INFO", "TELEMETRİ: Veri ele geçirildi.")
            except Exception as e:
                broadcast_log(client_id, "ERROR", f"UPLINK KOPTU: {str(e)[:100]}")
                if "InsufficientEvidenceError" in type(e).__name__ or "TargetPrivateError" in type(e).__name__:
                    raise e

        task_id = task_id or _new_task_id()
        max_attempts = _bounded_env_int("PINEAL_TASK_MAX_ATTEMPTS", 3, 1, 3)
        task_timeout = _bounded_env_int("PINEAL_TASK_TIMEOUT_SECONDS", 300, 1, 1800)
        for attempt in range(1, max_attempts + 1):
            try:
                broadcast_log(
                    client_id,
                    "INFO",
                    f"OPERASYON BAŞLATILIYOR (Deneme {attempt}/{max_attempts})...",
                )
                res = await asyncio.wait_for(
                    executor.execute_task(payload, task_id),
                    timeout=task_timeout,
                )
                broadcast_result(client_id, res)
                return
            except InsufficientEvidenceError:
                raise
            except Exception as e:
                broadcast_log(client_id, "ERROR", f"HATA: {type(e).__name__}: {str(e)[:100]}")
                if attempt == max_attempts:
                    broadcast_log(client_id, "ERROR", "SİSTEM PANİĞİ: MAKSİMUM DENEME AŞILDI.")
                    # [028] fix: terminal durum MUTLAKA WS'ye düşer; exception'ı
                    # yutmak UI'ı sonsuz 'işleniyor' durumunda asılı bırakır.
                    broadcast_result_error(
                        client_id, "failed",
                        f"SİSTEM PANİĞİ: MAKSİMUM DENEME AŞILDI ({max_attempts}/{max_attempts}).",
                        task_id,
                    )
                    return
    except InsufficientEvidenceError:
        broadcast_result_error(
            client_id, "halted_evidence", "DURDURULDU: YETERSİZ KANIT", task_id
        )
    except Exception as e:
        broadcast_result_error(
            client_id, "failed", f"SİSTEM PANİĞİ: {str(e)}", task_id
        )

def broadcast_result_error(client_id, status, msg, task_id: Optional[str] = None):
    broadcast_log(client_id, "ERROR", msg)
    payload = {"type": "result", "status": status}
    if task_id:
        payload["task_id"] = task_id
    _enqueue(client_id, ("result_error", payload))

async def _send_result_error(room: dict, data: dict):
    await _send_ws(room, json.dumps(data))

def broadcast_result(client_id, res):
    room = app.state.rooms.get(client_id)
    if room is None:
        return
    decision = _lifecycle(room).transition(res.task_id, res.status)
    if not decision.accepted:
        return

    def find(chain, name):
        for e in chain:
            if e["agent"] == name:
                return e["result"]
        return None

    def _dump_field(val):
        if val is None:
            return None
        if hasattr(val, "model_dump"):
            return val.model_dump(mode="json")
        return val

    _enqueue(client_id, ("result", {
        "type": "result",
        "task_id": res.task_id,
        "status": res.status,
        "evidence_chain": redact_structure(getattr(res, "evidence_chain", []) or []),
        "mirror": find(res.evidence_chain, "mirror_truth"),
        "reading": find(res.evidence_chain, "human_behavior"),
        "reso": find(res.evidence_chain, "resonance_calc"),
        "hook": find(res.evidence_chain, "pattern_interrupt"),
        # W4: zincir durumu final result'ta da korunur; UI snapshot bilgisini
        # kaybetmesin diye planned/completed/runs buraya da girer.
        "planned_agents": getattr(res, "planned_agents", []) or [],
        "completed_agents": getattr(res, "completed_agents", []) or [],
        "runs": {
            name: {
                "status": getattr(run, "status", None),
                "confidence": getattr(run, "confidence", None),
                "error_message": getattr(run, "error_message", None),
                "call_ids": list(getattr(run, "call_ids", []) or []),
                "output_summary": redact_structure(
                    getattr(run, "output_summary", None) or {}
                ),
                "provenance": redact_structure(
                    (getattr(run, "output_summary", None) or {}).get("_provenance")
                ),
            }
            for name, run in (getattr(res, "agent_runs", None) or {}).items()
        },
        "follower_audit": _dump_field(getattr(res, "follower_audit", None)),
        "timing_forensics": _dump_field(getattr(res, "timing_forensics", None)),
        "depth_report": _dump_field(getattr(res, "depth_report", None)),
        "visual_evidence": _dump_field(getattr(res, "visual_evidence", None)),
        "shadow_profile": _dump_field(getattr(res, "shadow_profile", None)),
        "osint_footprint": _dump_field(getattr(res, "osint_footprint", None)),
        "telemetry": getattr(res, "telemetry", None)
    }))

async def _send_result(room: dict, data: dict):
    result_telemetry = dict(data.get("telemetry") or {})
    result_telemetry["delivery"] = _delivery_status(room)
    result_telemetry["lifecycle"] = _lifecycle(room).metrics()
    data = {**data, "telemetry": result_telemetry}
    await _send_ws(room, json.dumps(data))

@app.post("/api/initiate")
async def api_initiate(req: InitiatePayload):
    if not rate_limit(f"initiate:{req.client_id}", "initiate"):
        return JSONResponse(
            {"error": {"code": "RATE_LIMITED", "message": "Çok fazla görev başlatma isteği; bir dakika içinde tekrar deneyin."}},
            status_code=429,
        )
    room = get_room(req.client_id)
    task_id = _new_task_id()
    _lifecycle(room).transition(task_id, "processing")
    mission = asyncio.create_task(run_mission(req, task_id))
    room["mission_tasks"][task_id] = mission
    mission.add_done_callback(lambda _task: room["mission_tasks"].pop(task_id, None))
    return {"status": "started", "task_id": task_id}

class VaultPayload(BaseModel):
    client_id: str
    x_cookie: str = ""
    api_key: str = ""
    tavily_key: str = ""
    serpapi_key: str = ""
    exa_key: str = ""
    local_url: str = ""
    local_model: str = ""
    # Optional so omitted != explicit false (UI toggle must be able to turn local OFF).
    use_local: Optional[bool] = None
    
@app.post("/api/vault")
async def api_vault(req: VaultPayload):
    vault = get_vault(req.client_id)
    executor = get_executor(req.client_id)
    if req.x_cookie:
        vault["x_cookie"] = req.x_cookie
        broadcast_log(req.client_id, "INFO", "KASA: Cookie belleğe mühürlendi.")
    if req.api_key:
        executor.llm_gateway.set_key(req.api_key, unlock_live=True)
        if shadow_executor is not None:
            shadow_executor.llm_gateway.set_key(req.api_key, unlock_live=True)
        if dialogue_manager is not None:
            dialogue_manager.llm.set_key(req.api_key, unlock_live=True)
        vault["or_key"] = True
        broadcast_log(req.client_id, "INFO", "KASA: API Anahtarı girildi. Ağ geçidi aktif — canlı LLM kilidi açıldı.")
        
    if req.local_url or req.local_model or req.use_local is not None:
        active = bool(req.use_local) if req.use_local is not None else bool(vault.get("use_local", False))
        executor.llm_gateway.set_local_config(
            base_url=req.local_url or None,
            model_name=req.local_model or None,
            active=active,
        )
        if req.use_local is not None:
            vault["use_local"] = active
        broadcast_log(req.client_id, "INFO", f"KASA: Yerel Kısıtlamasız LLM Yapılandırıldı ({req.local_model or 'Ollama/LM Studio'}).")

    if req.tavily_key or req.serpapi_key or req.exa_key:
        executor.search_engine.set_keys(tavily=req.tavily_key, serpapi=req.serpapi_key, exa=req.exa_key)
        vault["search_keys"] = True
        broadcast_log(req.client_id, "INFO", "KASA: Arama Motoru anahtarları mühürlendi.")
        
    return {"status": "secured"}

class OverridePayload(BaseModel):
    client_id: str
    fact: str
    tag: str

_override_lock = asyncio.Lock()

@app.post("/api/override")
async def api_override(req: OverridePayload):
    if req.fact.strip():
        executor = get_executor(req.client_id)
        mem_dir = executor.memory.storage_path
        lp = os.path.join(mem_dir, "learnings.json")
        async with _override_lock:
            def _read_learnings():
                return json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else []
            def _write_learnings(data):
                with open(lp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            learn = await asyncio.to_thread(_read_learnings)
            learn.append({"fact": req.fact.strip(), "tag": req.tag.strip(), "ts": datetime.now().isoformat(), "hash": hashlib.sha256(req.fact.strip().encode()).hexdigest()[:12]})
            await asyncio.to_thread(_write_learnings, learn)
        broadcast_log(req.client_id, "INFO", f"HAFIZA: Yeni konsept mühürlendi [{req.tag.strip()}]")
    return {"status": "sealed"}

@app.get("/api/telemetry")
async def api_telemetry(client_id: str):
    room = get_room(client_id)
    executor = room["executor"]
    vault = room["vault"]
    capability = await _scraper_capability()
    budget_reader = getattr(type(executor.llm_gateway), "budget_status", None)
    budget = budget_reader(executor.llm_gateway) if callable(budget_reader) else {}
    return {
        "core": True,
        "gateway": getattr(executor.llm_gateway, 'api_key', None) is not None,
        # geriye uyumlu anahtar; artik import basarisi degil, GERCEK yetenek
        "scraper": capability["instagram"],
        "vault": "x_cookie" in vault or bool(vault.get("or_key")),
        "search_engine": bool(vault.get("search_keys", False)) or bool(getattr(executor.search_engine, 'tavily_key', None)),
        # W5: gercek capability raporu
        "x_scraper": False,  # B4: X kazimasi devre disi birakildi
        "instagram_scraper": capability["instagram"],
        "browser_installed": capability["browser"],
        # P2-MALİYET: committed + in-flight reservations are read atomically.
        "llm_spend_usd": round(float(budget.get("spend_usd", 0.0)), 6),
        "llm_reserved_spend_usd": round(float(budget.get("reserved_usd", 0.0)), 6),
        "llm_spend_cap_usd": float(budget.get("cap_usd", 0.0)),
        "llm_active_reservations": int(budget.get("active_reservations", 0)),
        "telemetry_delivery": _delivery_status(room),
        "task_lifecycle": _lifecycle(room).metrics(),
        # Phase 9 decision B: visible, tested, and explicitly non-integrated.
        "rust_core": rust_core_status(),
        # [017]: açıkça kabul edilen takipsiz (fiyatsız) model çağrı sayısı
        "llm_unpriced_calls": int(getattr(executor.llm_gateway, "unpriced_calls", 0)),
    }

class SocidExtractPayload(BaseModel):
    url: str


class MaigretScanPayload(BaseModel):
    username: str
    limit: Optional[int] = None
    timeout: Optional[int] = None


@app.post("/api/experimental/maigret/scan")
async def maigret_scan(payload: MaigretScanPayload):
    """Kullanıcı adını maigret DB'sinde tarar (FAZ 2).

    Kapı: ENABLE_MAIGRET=true (varsayılan kapalı). Dürüst sonuç: kayıt
    çıkmazsa `available:false` + makine-okunur sebep; site/hesap uydurulmaz.
    """
    from agent_core.services.maigret_scanner import scan_username
    result = await scan_username(
        payload.username, limit=payload.limit, site_timeout=payload.timeout
    )
    return result.model_dump()


class HoleheScanPayload(BaseModel):
    email: str
    limit: Optional[int] = None
    timeout: Optional[int] = None


@app.post("/api/experimental/holehe/scan")
async def holehe_scan(payload: HoleheScanPayload):
    """E-postanın sitelerdeki kaydını holehe ile tarar (FAZ 3, deneysel).

    Kapı: ENABLE_HOLEHE=true (varsayılan kapalı). Dürüst sonuç: kayıt
    çıkmazsa `available:false` + makine-okunur sebep; site uydurulmaz.
    holehe'nin istisnaları rateLimit olarak maskelemesi hata sayılır —
    kapalı ağda asla "kayıtlı değil" iddia edilmez.
    """
    from agent_core.services.holehe_scanner import scan_email
    result = await scan_email(
        payload.email, limit=payload.limit, site_timeout=payload.timeout
    )
    return result.model_dump()


class CrawlFetchPayload(BaseModel):
    url: str


@app.post("/api/experimental/crawl/fetch")
async def crawl_fetch(payload: CrawlFetchPayload):
    """Public-web sayfasını crawl4ai ile LLM-dostu metne çevirir (FAZ 4).

    Kapı: ENABLE_CRAWL4AI=true (varsayılan kapalı; renderer=http tarayıcı
    binary'si gerektirmez). Dürüst sonuç: içerik çekilemezse `available:false`
    + makine-okunur sebep; ASLA uydurma içerik döner. SSRF guard'lı.
    """
    from agent_core.services.crawl_enricher import fetch_readable
    return (await fetch_readable(payload.url)).model_dump()


@app.get("/api/experimental/stealth")
async def stealth_resolve(provider: Optional[str] = None):
    """STEALTH_PROVIDER seçimini ve dürüst kullanılabilirliği gösterir (FAZ 5).

    Salt-okunur: tarayıcı başlatmaz, binary indirmeyi TETİKLEMEZ. invisible/
    cloak yalnız operatörün env ile gösterdiği binary varsa available döner;
    yoksa makine-okunur sebep (binary_missing / library_missing).
    """
    from agent_core.services.stealth_provider import resolve_stealth
    return resolve_stealth(override=provider).model_dump()


@app.post("/api/experimental/socid/extract")
async def socid_extract(payload: SocidExtractPayload):
    """Profil URL'sinden yapılandırılmış kimlik kaydı çıkarır (socid-extractor).

    Dürüst sonuç sözleşmesi: kayıt çıkmazsa `available:false` + makine-okunur
    sebep döner; alan uydurulmaz. SSRF guard'lı (private/loopback engelli).
    """
    from agent_core.services.socid_enricher import extract_profile
    record = await extract_profile(payload.url)
    return record.model_dump()


@app.post("/api/experimental/shadow/analyze")
async def shadow_analyze(profile: dict):
    """Dark Triad analizi"""
    if shadow_executor is None:
        return {"error": "Shadow Protocol yüklü değil"}
    from agent_core.psychology.dark_triad import DarkTriadAnalyzer
    analyzer = DarkTriadAnalyzer()
    result = analyzer.analyze(profile)
    return result.model_dump()

@app.post("/api/experimental/shadow/generate")
async def shadow_generate(task: dict):
    """Shadow mesaj üretimi"""
    if shadow_executor is None:
        return {"error": "Shadow Protocol yüklü değil"}
    result = await shadow_executor.execute(task)
    return result.model_dump()

class ChatPayload(BaseModel):
    task_id: str
    target_profile: dict
    user_profile: dict
    target_message: str

@app.post("/api/experimental/chat/respond")
async def chat_respond(payload: ChatPayload):
    """Hedefin mesajına otonom karşı hamle üretir"""
    if dialogue_manager is None:
        return {"error": "Gölge Sohbet modülü yüklü değil"}
    
    try:
        if payload.task_id not in dialogue_manager.sessions:
            dialogue_manager.start_session(payload.task_id, payload.target_profile, payload.user_profile)
            
        res = await dialogue_manager.generate_response(payload.task_id, payload.target_message)
        return res.model_dump()
    except Exception as e:
        logger.error("Dialogue generation failed: %s", type(e).__name__)
        return {"error": {"code": "DIALOGUE_FAILED", "message": type(e).__name__}}

class AspasiaChatPayload(BaseModel):
    client_id: str
    user_message: str
    model_override: Optional[str] = None
    image_data: Optional[str] = None

@app.post("/api/aspasia/chat")
async def aspasia_chat(payload: AspasiaChatPayload):
    """Aspasia Kokpit Şefi ile canlı Sokratik diyalog"""
    if not rate_limit(f"aspasia:{payload.client_id}", "aspasia"):
        return JSONResponse(
            {"error": {"code": "RATE_LIMITED", "message": "Aspasia yoğun; kısa bir mola verin."}},
            status_code=429,
        )
    room = get_room(payload.client_id)
    aspasia = room.get("aspasia") or aspasia_chief
    if not aspasia:
        return {"error": {"code": "ASPASIA_UNAVAILABLE", "message": "Aspasia Kokpit Şefi yüklenemedi"}}
    
    resp = await aspasia.chat(payload.user_message, room, payload.model_override, payload.image_data)
    return resp.model_dump()

class AlternativeAuthorizationPayload(BaseModel):
    client_id: str
    alternative: str
    approved: bool


def _extract_handle_from_url(url: str) -> str:
    """X/Instagram URL'sinden kullanıcı adı (subject) çıkarır."""
    import re
    if not url:
        return ""
    needle = re.search(r"(?:instagram\.com|x\.com|twitter\.com)/([^/?#]+)", url)
    if needle:
        return needle.group(1).strip().lstrip("@").lower()
    return url.split("?")[0].rstrip("/").split("/")[-1].replace("@", "").lower()


async def _run_public_web_research(url: str, search_engine: Any) -> Dict[str, Any]:
    """Yetki verilmiş alternatif: kanıt kaynaklı public-web araması.

    Sözleşme (sahte veri YASAK):
    - Biyografi/gönderi/kişilik ÜRETİLMEZ; yalnızca gerçek arama kayıtları
      döner (source_url + provider + content).
    - Subject matching: hedef kullanıcı adı kaynak URL'sinde veya içeriğinde
      geçmeyen sonuçlar düşürülür (yanlış kişi eşleşmesi engeli).
    - Sağlayıcı yok/çöktü -> available=False; sonuç yok -> no_results.
    """
    handle = _extract_handle_from_url(url)
    if not handle:
        return {
            "status": "invalid_target", "available": False,
            "query": "", "results": [], "matched_username": "",
            "total_results_searched": 0,
            "searched_at": datetime.now().isoformat(),
            "note": "URL'den hedef kullanıcı adı çıkarılamadı.",
        }

    query = f'"{handle}"'
    outcome = await search_engine.search(query, num_results=8)
    if not getattr(outcome, "available", False):
        return {
            "status": "unavailable", "available": False, "query": query,
            "results": [], "matched_username": handle,
            "total_results_searched": 0,
            "searched_at": datetime.now().isoformat(),
            "note": getattr(outcome, "error", None) or "Arama sağlayıcısı kullanılamadı.",
        }

    raw = getattr(outcome, "results", []) or []
    matched = [
        {
            "source_url": r.source_url,
            "provider": r.provider,
            "content": r.content,
            "subject_match": True,
        }
        for r in raw
        if handle in (r.source_url or "").lower()
        or handle in (r.content or "").lower()
    ]
    # socid-extractor zenginleştirmesi: eşleşen kaynak URL'lerden kararlı kimlik
    # kaydı çıkmaya çalışılır. Kütüphane yok/ağ yok/kayıt yoksa alan EKLENMEZ —
    # sonuç sözleşmesi bozulmaz (dürüst boş).
    try:
        socid_records = await socid_enricher.enrich_urls(
            [m["source_url"] for m in matched], limit=3
        )
        by_url = {r.source_url: r for r in socid_records}
        for m in matched:
            rec = by_url.get(m["source_url"])
            if rec is not None:
                m["socid"] = rec.model_dump()
        if socid_records:
            socid_note = f" {len(socid_records)} sonuçtan yapılandırılmış kimlik kaydı çıkarıldı."
        else:
            socid_note = ""
    except Exception as exc:  # zenginleştirme asıl sonucu asla bozmasın
        logger.warning("socid enrichment skipped: %s: %s", type(exc).__name__, str(exc)[:80])
        socid_note = ""
    # [FAZ 4] Crawl4AI okunabilir-metin zenginleştirmesi. Kapı:
    # ENABLE_CRAWL4AI (varsayılan kapalı → davranış birebir aynı). Yalnız
    # available=True sonuçlar `crawl` alanına girer; hatalar alan EKLEMEZ
    # (dürüst boş) ve asıl araştırma sonucunu asla bozmaz.
    crawl_note = ""
    try:
        if crawl_enricher.is_enabled() and matched:
            crawled = 0
            for m in matched[:crawl_enricher.research_limit()]:
                res = await crawl_enricher.fetch_readable(m["source_url"])
                if res.available:
                    m["crawl"] = res.model_dump()
                    crawled += 1
            if crawled:
                crawl_note = f" {crawled} sonuca crawl4ai ile okunabilir metin çekildi."
    except Exception as exc:  # zenginleştirme asıl sonucu asla bozmasın
        logger.warning("crawl4ai enrichment skipped: %s: %s", type(exc).__name__, str(exc)[:80])

    if matched:
        status = "ok"
        note = f"{len(matched)}/{len(raw)} sonuç hedef kullanıcı adıyla eşleşti." + socid_note + crawl_note
    elif raw:
        status = "no_subject_match"
        note = f"Arama yapıldı ({len(raw)} sonuç) ama hiçbiri hedef kullanıcı adıyla eşleşmedi; sonuç gösterilmiyor (yanlış kişi eşleşmesi engeli)."
    else:
        status = "no_results"
        note = "Arama yapıldı, hiç sonuç döndü."

    return {
        "status": status,
        "available": True,
        "query": query,
        "results": matched,
        "matched_username": handle,
        "total_results_searched": len(raw),
        "searched_at": datetime.now().isoformat(),
        "note": note,
    }


@app.post("/api/scraper/authorize-alternative")
async def authorize_scraper_alternative(req: AlternativeAuthorizationPayload):
    room = get_room(req.client_id)
    pending = room.get("pending_alternative_authorization")
    if not pending:
        return {"status": "no_pending_authorization"}
    if not req.approved or req.alternative not in pending["alternatives"]:
        room.pop("pending_alternative_authorization", None)
        return {"status": "declined"}
    # Authorization is recorded; provider execution is a separate explicit
    # route and must not fabricate an X profile from unrelated sources.
    room["authorized_alternatives"] = room.get("authorized_alternatives", []) + [{
        "alternative": req.alternative,
        "url": pending["url"],
        "authorized_at": datetime.now().isoformat(),
    }]

    if req.alternative == "public_web_search":
        executor = get_executor(req.client_id)
        research = await _run_public_web_research(pending["url"], executor.search_engine)
        room["web_research"] = research
        room.pop("pending_alternative_authorization", None)
        broadcast_log(
            req.client_id, "INFO",
            f"ALTERNATİF ARAŞTIRMA: {research['note']}",
        )
        return {"status": "research_completed", "alternative": req.alternative,
                "research": research}

    room.pop("pending_alternative_authorization", None)
    return {"status": "authorized", "alternative": req.alternative}


class IntervenePayload(BaseModel):
    client_id: str
    action_type: str
    target_agent: Optional[str] = None
    parameters: dict = Field(default_factory=dict)
    reason: str = ""


class InterventionRecord(BaseModel):
    client_id: str
    action_type: str
    target_agent: Optional[str] = None
    parameters: dict = Field(default_factory=dict)
    reason: str = ""
    requested_at: str
    outcome: str


@app.post("/api/executor/intervene")
async def executor_intervene(req: IntervenePayload):
    """Record intervention requests without mutating shared executor safety state."""
    room = get_room(req.client_id)
    record = InterventionRecord(
        client_id=req.client_id,
        action_type=req.action_type,
        target_agent=req.target_agent,
        parameters=req.parameters,
        reason=req.reason,
        requested_at=datetime.now().isoformat(),
        outcome="review_required",
    )
    room.setdefault("interventions", []).append(record.model_dump())

    # These actions previously rewrote uncertainty or deleted agents from the
    # room's shared executor. They are now auditable requests, not bypasses.
    if req.action_type in {"OVERRIDE_CONFIDENCE", "SKIP_AGENT", "HALT"}:
        broadcast_log(req.client_id, "WARNING", f"MÜDAHALE KAYDEDİLDİ: {req.action_type}; otomatik uygulanmadı.")
        return {
            "status": "review_required",
            "message": "Talep kaydedildi. Kanıt/güvenlik kuralları otomatik olarak değiştirilmedi.",
            "intervention": record.model_dump(),
        }

    return {
        "status": "acknowledged",
        "message": "Müdahale talebi kaydedildi; uygulanmadan önce inceleme gerekir.",
        "intervention": record.model_dump(),
    }

class InterpreterPayload(BaseModel):
    client_id: str
    prompt: str
    auto_run: bool = False

@app.post("/api/experimental/interpreter/execute")
async def interpreter_execute(req: InterpreterPayload):
    """Open Interpreter ile otonom kod icra eder"""
    import os
    if os.getenv("ENABLE_INTERPRETER", "false").lower() != "true":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Interpreter endpoint is disabled by default for security.")
        
    room = get_room(req.client_id)
    executor = room.get("executor")
    interpreter_agent = executor.agents.get("interpreter")
    
    if not interpreter_agent:
        return {"error": "Interpreter Agent aktif değil"}
        
    broadcast_log(req.client_id, "INFO", f"INTERPRETER: Görev icra ediliyor -> {req.prompt[:60]}...")
    res = await interpreter_agent.execute_task(
        prompt=req.prompt,
        api_key=executor.llm_gateway.api_key,
        auto_run=req.auto_run
    )
    
    if res.status == "success":
        broadcast_log(req.client_id, "INFO", "INTERPRETER: İcra başarıyla tamamlandı.")
    else:
        broadcast_log(req.client_id, "ERROR", f"INTERPRETER HATA: {res.error_message}")
        
    return res.model_dump()

# --- Görev geçmişi ve veri silme (FAZ 3 / etik çerçeve: kişisel veri hedefli sistemde
#     retention hakkı): bellekteki kanıt dosyaları listelenir ve KALICI olarak silinir. ---

def _read_tasks_sync(storage: str):
    tasks = []
    if os.path.isdir(storage):
        for fn in sorted(os.listdir(storage)):
            if not fn.endswith(".json") or fn == "learnings.json":
                continue
            task_id = fn[:-5]
            try:
                path = safe_child_path(storage, fn)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not isinstance(data.get("evidence", []), list):
                    raise ValueError("invalid canonical memory schema")
                tasks.append({
                    "task_id": data.get("task_id", task_id),
                    "last_updated": data.get("last_updated"),
                    "evidence_count": len(data.get("evidence", [])),
                    "confidence": data.get("confidence"),
                    "memory_state": "READY",
                    "memory_error_code": None,
                })
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                # A malformed task remains visible and is never represented as
                # an absent task in retention/operations APIs.
                tasks.append({
                    "task_id": task_id,
                    "last_updated": None,
                    "evidence_count": None,
                    "confidence": None,
                    "memory_state": "CORRUPTED",
                    "memory_error_code": "MEMORY_CORRUPTED",
                })
    return tasks

@app.get("/api/tasks")
async def api_list_tasks(client_id: str):
    room = get_room(client_id)
    storage = room["executor"].memory.storage_path
    tasks = await asyncio.to_thread(_read_tasks_sync, storage)
    active = list(room.get("active_tasks", {}).keys())
    return {"tasks": tasks, "active_tasks": active}


def _terminate_mission(client_id: str, task_id: str, action: str, reason: str):
    room = get_room(client_id)
    run = _lifecycle(room).get_run(task_id)
    if run is None:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "Task not found"}},
            status_code=404,
        )
    decision = _lifecycle(room).terminate(task_id, action)
    if not decision.accepted:
        return JSONResponse(
            {"error": {"code": "TASK_ALREADY_TERMINAL", "message": "Task already reached a terminal state"}},
            status_code=409,
        )

    mission = room.get("mission_tasks", {}).get(task_id)
    if mission is not None and not mission.done():
        mission.cancel()
    if decision.outcome != "IDEMPOTENT":
        if action == "cancel":
            broadcast_event(client_id, TaskCancelledEvent(
                task_id=task_id,
                agent_name="PinealExecutor",
                reason=reason or "Cancelled by user",
            ))
            broadcast_result_error(client_id, "cancelled", "GÖREV İPTAL EDİLDİ", task_id)
        else:
            broadcast_event(client_id, ErrorHaltEvent(
                task_id=task_id,
                agent_name="PinealExecutor",
                error_code="USER_HALT",
                error_message=reason or "Halted by user",
                severity=Severity.Warning,
            ))
            broadcast_result_error(
                client_id,
                "halted_user",
                "GÖREV KULLANICI TARAFINDAN DURDURULDU",
                task_id,
            )
    return {
        "status": "cancelled" if action == "cancel" else "halted_user",
        "task_id": task_id,
        "outcome": decision.outcome,
    }


@app.post("/api/tasks/{task_id}/cancel")
async def api_cancel_task(task_id: str, client_id: str, reason: str = ""):
    return _terminate_mission(client_id, task_id, "cancel", reason)


@app.post("/api/tasks/{task_id}/halt")
async def api_halt_task(task_id: str, client_id: str, reason: str = ""):
    return _terminate_mission(client_id, task_id, "halt", reason)


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str, client_id: str):
    """Bir görevin tüm izlerini kalıcı siler (bellek dosyası + aktif snapshot)."""
    room = get_room(client_id)

    try:
        validate_identifier(task_id, field="task_id")
        mem_path = safe_child_path(
            room["executor"].memory.storage_path,
            f"{task_id}.json",
        )
    except ValueError:
        return JSONResponse(
            {"error": {"code": "INVALID_TASK_ID", "message": "Invalid task identifier"}},
            status_code=400,
        )
    removed_snapshot = room.get("active_tasks", {}).pop(task_id, None)
    file_deleted = False
    if os.path.exists(mem_path):
        try:
            os.remove(mem_path)
            file_deleted = True
        except OSError as e:
            return JSONResponse(
                {"error": {"code": "DELETE_FAILED", "message": redact_text(e)[:120]}},
                status_code=500,
            )

    if not removed_snapshot and not file_deleted:
        return JSONResponse(
            {"error": {"code": "NOT_FOUND", "message": f"Görev bulunamadı: {task_id}"}},
            status_code=404,
        )

    broadcast_log(client_id, "INFO", f"VERİ SİLME: '{task_id}' görev izleri kalıcı olarak silindi (retention).")
    return {
        "status": "deleted",
        "task_id": task_id,
        "snapshot_removed": removed_snapshot is not None,
        "memory_file_deleted": file_deleted,
    }


static_dir = "frontend/dist" if os.path.exists("frontend/dist") else "frontend"
os.makedirs(static_dir, exist_ok=True)
# Sona ekliyoruz ki api rotaları statik dosyalardan önce ezilmesin
app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
