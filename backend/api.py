try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from fastapi import FastAPI, WebSocket, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import asyncio
import json
import os
import hashlib
import time
from datetime import datetime
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

try:
    from agent_core.task_executor import PinealExecutor, InsufficientEvidenceError
except Exception:
    from task_executor import PinealExecutor, InsufficientEvidenceError

try:
    from scraper import scrape_readonly
except Exception:
    scrape_readonly = None

try:
    from agent_core.scraper.instagram_ghost import InstagramGhostScraper
except Exception:
    InstagramGhostScraper = None

try:
    from agent_core.shadow.shadow_executor import ShadowExecutor
    shadow_executor = ShadowExecutor()
except Exception:
    shadow_executor = None

try:
    from agent_core.chat.dialogue_manager import DialogueManager
    dialogue_manager = DialogueManager()
except Exception:
    dialogue_manager = None

try:
    from agent_core.aspasia.aspasia_chief import AspasiaChief
    aspasia_chief = AspasiaChief()
except Exception:
    aspasia_chief = None

@asynccontextmanager
async def lifespan(application: FastAPI):
    yield
    # Kapanista oda gonderici task'lerini iptal et (temiz kapanis)
    for room in application.state.rooms.values():
        task = room.get("sender_task")
        if task and not task.done():
            task.cancel()
    application.state.rooms.clear()

app = FastAPI(title="PINEAL-HERETIC v2.0 API", lifespan=lifespan)

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth (FAZ 3): PINEAL_TOKEN tanimliysa tum /api/* X-API-Key ister;
# tanimli degilse sistem acik calisir (yerel tek kullanicili arac, geriye uyumluluk). ---
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = os.getenv("PINEAL_TOKEN")
    require_auth = os.getenv("PINEAL_REQUIRE_AUTH", "false").lower() == "true"
    
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        if require_auth and not token:
            return JSONResponse(
                {"error": {"code": "FORBIDDEN", "message": "Production mode requires PINEAL_TOKEN to be set"}},
                status_code=403,
            )
        if token and request.headers.get("x-api-key") != token:
            return JSONResponse(
                {"error": {"code": "UNAUTHORIZED", "message": "X-API-Key gerekli veya hatalı"}},
                status_code=401,
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
RATE_LIMITS = {"initiate": (5, 60), "aspasia": (20, 60)}  # (istek, pencere_sn)
_rate_buckets: Dict[str, deque] = defaultdict(deque)

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
        serpapi = vault.get("serpapi_key") or os.getenv("SERPAPI_KEY")
        exa = vault.get("exa_key") or os.getenv("EXA_API_KEY")
        if tavily or serpapi or exa:
            executor.search_engine.set_keys(tavily=tavily, serpapi=serpapi, exa=exa)
            vault["search_keys"] = True
        use_local = vault.get("use_local", False)
        executor.llm_gateway.use_local = use_local

        app.state.rooms[client_id] = {
            "executor": executor,
            "vault": vault,
            "websockets": set(),
            "logs": [],
            "aspasia": AspasiaChief(llm_gateway=executor.llm_gateway) if AspasiaChief else None,
            "queue": asyncio.Queue(maxsize=2000),
            "sender_task": None,
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

def _enqueue(client_id: str, item: tuple):
    """Sirali ekleme; tasma durumunda en eski mesaj atilir (sessiz kayip yok, tasma yok)."""
    room = app.state.rooms.get(client_id)
    if not room:
        return
    if room.get("sender_task") is None or room["sender_task"].done():
        try:
            loop = asyncio.get_running_loop()
            room["sender_task"] = loop.create_task(_room_sender(room))
        except RuntimeError:
            pass
    q: asyncio.Queue = room["queue"]
    try:
        q.put_nowait(item)
    except asyncio.QueueFull:
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass

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
    _enqueue(client_id, ("log", (level, msg)))

def sync_log(client_id: str, level: str, msg: str):
    broadcast_log(client_id, level, msg)

async def _send_event(room: dict, event: Any):
    from agent_core.schemas.telemetry import TelemetryEvent
    telemetry = TelemetryEvent(event=event)
    if "events" not in room: room["events"] = []
    room["events"].append(telemetry)
    await _send_ws(room, telemetry.model_dump_json())

def broadcast_event(client_id: str, event: Any):
    _enqueue(client_id, ("event", event))

def sync_event(client_id: str, event: Any):
    broadcast_event(client_id, event)

async def _send_snapshot(room: dict, snapshot: Any):
    def _dump_field(val):
        if val is None:
            return None
        if hasattr(val, "model_dump"):
            return val.model_dump(mode="json")
        return val

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
        "telemetry": getattr(snapshot, "telemetry", None),
        "runs": {
            name: {
                "status": getattr(r, "status", None),
                "confidence": getattr(r, "confidence", None),
                "started_at": r.started_at.isoformat() if getattr(r, "started_at", None) else None,
                "completed_at": r.completed_at.isoformat() if getattr(r, "completed_at", None) else None,
                "error_message": getattr(r, "error_message", None),
            }
            for name, r in snapshot.agent_runs.items()
        }
    })
    if "active_tasks" not in room:
        room["active_tasks"] = {}
    room["active_tasks"][snapshot.task_id] = snapshot
    await _send_ws(room, payload)

def broadcast_snapshot(client_id: str, snapshot: Any):
    _enqueue(client_id, ("snapshot", snapshot))

def sync_snapshot(client_id: str, snapshot: Any):
    broadcast_snapshot(client_id, snapshot)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    # FAZ 3: token kipinde WS de korunur (?token=... query parametresi)
    token = os.getenv("PINEAL_TOKEN")
    if token and websocket.query_params.get("token") != token:
        await websocket.close(code=1008)
        return
    await websocket.accept()
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
