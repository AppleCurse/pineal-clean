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
    if token and request.url.path.startswith("/api/") and request.method != "OPTIONS":
        if request.headers.get("x-api-key") != token:
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
    # [037] fix: aggressiveness/evidence_th kabul ediliyordu ama HİÇBİR davranışa
    # bağlanmamıştı (ölü API sözleşmesi). Kaldırıldı; eşik ayarı gerekiyorsa
    # DecisionConfig üzerinden gerçek davranışla bağlanmalı. Eski istemcilerin
    # bu alanları göndermesi pydantic tarafından sessizce yok sayılır.

def _effective_scraper_type(url: str, requested: str) -> str:
    """URL platformuna göre tarayıcı seç ([023] fix: platform registry).

    Instagram adresi X tarayıcısına gitmesin diye URL platform tespiti
    önceliklidir; ancak tanınmayan platformda kullanıcı seçimi GEÇERLİ
    DEĞİLDİR: URL'nin son path segmentini Instagram adı gibi kullanıp
    yanlış hedefi kazımak misattribution'dır. Tanınmayan platform ->
    unsupported_web (run_mission analizi başlatmadan durur).
    """
    u = (url or "").lower()
    if "instagram.com" in u:
        return "instagram"
    if "x.com" in u or "twitter.com" in u:
        return "x"
    return "unsupported_web"

def _new_task_id() -> str:
    """[029] fix: saniye-çözünürlüklü op_HHMMSS çakışıyordu; aynı saniyede iki
    görev (farklı client'lar dahil) aynı memory dosyasında birleşiyordu.
    Tarihi saniye + uuid4 öneki -> CanonicalMemory task_id regex'i ile uyumlu."""
    import uuid
    return f"op_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _ig_target_profile_update(ig_data: Any) -> dict:
    """InstagramProfile -> target_profile payload alanları ([024]/[025]/[026] fix).

    Sözleşme (sahte veri YASAK):
    - Sentetik "Instagram Profili: ..." postu ÜRETİLMEZ; caption yoksa "" kalır.
    - posts / post_times / posts_meta AYNI post sırasıyla index-hizalıdır;
      frequency_engine index bazlı eşleştirme yapar, hizasız listeler
      caption'a başka postun zamanını yanlış eşleştirebilir.
    - following=None "ölçülmedi" demektir; 0 ölçümdür, birbirine karışmaz.
    """
    posts = ig_data.posts or []
    return {
        "username": "@" + ig_data.username,
        "bio": ig_data.biography or "",
        "posts": [p.caption or "" for p in posts],
        # Zaman damgası yoksa "" (None değil): str() ile "None" metnine
        # dönüşüp quote_guard source'larına sızmasın.
        "post_times": [p.taken_at.isoformat() if p.taken_at else "" for p in posts],
        "posts_meta": [
            {"like_count": p.like_count, "comment_count": p.comment_count}
            for p in posts
        ],
        "images": [p.display_url for p in posts],
        "followers": ig_data.follower_count or 0,
        "following": ig_data.following_count,  # None = ölçülmedi ([024])
        "is_private": ig_data.is_private,
    }


async def run_mission(req: InitiatePayload):
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
            broadcast_log(client_id, "INFO", f"UPLINK: Hedefe sızılıyor -> {req.url} [{effective_type.upper()}]")
            try:
                from playwright.async_api import async_playwright
                try:
                    from playwright_stealth import Stealth
                    stealth_engine = Stealth()
                except Exception:
                    stealth_engine = None

                async with async_playwright() as p:
                    browser = None
                    ctx = None
                    page = None
                    try:
                        launch_kwargs = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
                        chrome_paths = [
                            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                        ]
                        for cp in chrome_paths:
                            if os.path.exists(cp):
                                launch_kwargs["executable_path"] = cp
                                break

                        browser = await p.chromium.launch(**launch_kwargs)
                        ctx_kwargs = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                        
                        clean_username = req.url.split("?")[0].rstrip("/").split("/")[-1].replace("@", "")

                        if effective_type == "instagram" and InstagramGhostScraper:
                            ctx = await browser.new_context(**ctx_kwargs)
                            if cookie and "sessionid" in cookie:
                                parsed = []
                                for part in cookie.split(";"):
                                    if "=" in part:
                                        k, v = part.split("=", 1)
                                        parsed.append({"name": k.strip(), "value": v.strip(), "domain": ".instagram.com", "path": "/"})
                                if parsed:
                                    await ctx.add_cookies(parsed)
                            
                            page = await ctx.new_page()
                            if stealth_engine:
                                await stealth_engine.apply_stealth_async(page)
                            ig_scraper = InstagramGhostScraper(vault_cookies={"sessionid": cookie} if cookie else None)
                            ig_data = await ig_scraper.scrape_async(clean_username, playwright_page=page)
                            
                            # [024]/[025]/[026]: hizalı gerçek alanlar; sentetik
                            # post ÜRETİLMEZ, following=None ölçülmedi demektir.
                            payload["target_profile"].update(_ig_target_profile_update(ig_data))
                            
                        # [016] X buraya asla ulaşmaz: effective_type == "x"
                        # run_mission başında awaiting_authorization'a döner.
                        # [023] cross/generic dalları kaldırıldı: tanınmayan
                        # platform unsupported_web ile yukarıda açıkça durur;
                        # scrape_readonly (X-unsupported) çağrılamaz hale geldi.
                    finally:
                        for resource_name, resource in (("page", page), ("context", ctx), ("browser", browser)):
                            if resource:
                                try:
                                    await resource.close()
                                except Exception as cleanup_error:
                                    broadcast_log(client_id, "WARNING", f"SCRAPER CLEANUP: {resource_name} kapanamadı: {str(cleanup_error)[:80]}")
                        
                broadcast_log(client_id, "INFO", "TELEMETRİ: Veri ele geçirildi.")
            except Exception as e:
                broadcast_log(client_id, "ERROR", f"UPLINK KOPTU: {str(e)[:100]}")
                if "InsufficientEvidenceError" in type(e).__name__ or "TargetPrivateError" in type(e).__name__:
                    raise e
        
        task_id = _new_task_id()
        for attempt in range(1, 4):
            try:
                broadcast_log(client_id, "INFO", f"OPERASYON BAŞLATILIYOR (Deneme {attempt}/3)...")
                res = await executor.execute_task(payload, task_id)
                broadcast_result(client_id, res)
                return
            except InsufficientEvidenceError:
                raise
            except Exception as e:
                broadcast_log(client_id, "ERROR", f"HATA: {type(e).__name__}: {str(e)[:100]}")
                if attempt == 3:
                    broadcast_log(client_id, "ERROR", "SİSTEM PANİĞİ: MAKSİMUM DENEME AŞILDI.")
                    # [028] fix: terminal durum MUTLAKA WS'ye düşer; exception'ı
                    # yutmak UI'ı sonsuz 'işleniyor' durumunda asılı bırakır.
                    broadcast_result_error(
                        client_id, "failed",
                        "SİSTEM PANİĞİ: MAKSİMUM DENEME AŞILDI (3/3).",
                    )
                    return
    except InsufficientEvidenceError:
        broadcast_result_error(client_id, "halted_evidence", "DURDURULDU: YETERSİZ KANIT")
    except Exception as e:
        broadcast_result_error(client_id, "failed", f"SİSTEM PANİĞİ: {str(e)}")

def broadcast_result_error(client_id, status, msg):
    broadcast_log(client_id, "ERROR", msg)
    _enqueue(client_id, ("result_error", {"type": "result", "status": status}))

async def _send_result_error(room: dict, data: dict):
    await _send_ws(room, json.dumps(data))

def broadcast_result(client_id, res):
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
        "status": res.status,
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
    await _send_ws(room, json.dumps(data))

@app.post("/api/initiate")
async def api_initiate(req: InitiatePayload, background_tasks: BackgroundTasks):
    if not rate_limit(f"initiate:{req.client_id}", "initiate"):
        return JSONResponse(
            {"error": {"code": "RATE_LIMITED", "message": "Çok fazla görev başlatma isteği; bir dakika içinde tekrar deneyin."}},
            status_code=429,
        )
    background_tasks.add_task(run_mission, req)
    return {"status": "started"}

class VaultPayload(BaseModel):
    client_id: str
    x_cookie: str = ""
    api_key: str = ""
    tavily_key: str = ""
    serpapi_key: str = ""
    exa_key: str = ""
    local_url: str = ""
    local_model: str = ""
    use_local: bool = False
    
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
        
    if req.local_url or req.local_model or req.use_local:
        executor.llm_gateway.set_local_config(
            base_url=req.local_url or None,
            model_name=req.local_model or None,
            active=req.use_local
        )
        vault["use_local"] = req.use_local
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
    executor = get_executor(client_id)
    vault = get_vault(client_id)
    capability = await _scraper_capability()
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
        # P2-MALİYET: oturum boyu tahmini harcama + aktif limit
        "llm_spend_usd": round(float(getattr(executor.llm_gateway, "spend_usd", 0.0)), 6),
        "llm_spend_cap_usd": float(getattr(executor.llm_gateway, "spend_cap_usd", 0.0)),
    }

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
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

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
    if matched:
        status = "ok"
        note = f"{len(matched)}/{len(raw)} sonuç hedef kullanıcı adıyla eşleşti."
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
            if not fn.endswith(".json"):
                continue
            path = os.path.join(storage, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tasks.append({
                    "task_id": data.get("task_id", fn[:-5]),
                    "last_updated": data.get("last_updated"),
                    "evidence_count": len(data.get("evidence", [])),
                    "confidence": data.get("confidence"),
                })
            except Exception:
                continue
    return tasks

@app.get("/api/tasks")
async def api_list_tasks(client_id: str):
    room = get_room(client_id)
    storage = room["executor"].memory.storage_path
    tasks = await asyncio.to_thread(_read_tasks_sync, storage)
    active = list(room.get("active_tasks", {}).keys())
    return {"tasks": tasks, "active_tasks": active}


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str, client_id: str):
    """Bir görevin tüm izlerini kalıcı siler (bellek dosyası + aktif snapshot)."""
    room = get_room(client_id)
    removed_snapshot = room.get("active_tasks", {}).pop(task_id, None)

    mem_path = os.path.join(room["executor"].memory.storage_path, f"{task_id}.json")
    file_deleted = False
    if os.path.exists(mem_path):
        try:
            os.remove(mem_path)
            file_deleted = True
        except OSError as e:
            return JSONResponse(
                {"error": {"code": "DELETE_FAILED", "message": str(e)[:120]}},
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
