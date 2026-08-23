from fastapi import FastAPI, WebSocket, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import asyncio
import json
import os
import hashlib
import time
from datetime import datetime

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
    aggressiveness: float
    evidence_th: int
    scraper_type: str = "x"

def _effective_scraper_type(url: str, requested: str) -> str:
    """URL'nin platformuna göre tarayıcı seç (FIX: instagram adresi X tarayıcısına
    gitmesin). Tanınmayan adreslerde kullanıcının seçimine saygı duyar."""
    u = (url or "").lower()
    if "instagram.com" in u:
        return "instagram"
    if "x.com" in u or "twitter.com" in u:
        return "x"
    return requested

async def run_mission(req: InitiatePayload):
    client_id = req.client_id
    executor = get_executor(client_id)
    vault = get_vault(client_id)
    
    try:
        user_rituals = [r.strip() for r in req.rituals.split(",") if r.strip()] if req.rituals else ["Gece stüdyo kayıtları", "Analog ses tasarımı"]
        user_playlist = [req.playlist.strip()] if req.playlist and req.playlist.strip() else ["Dark Jazz", "Ambient"]
        user_envies = [e.strip() for e in req.envies.split(",") if e.strip()] if req.envies else ["Sahici ve derin diyalog"]

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
        if req.url:
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
                        
                        is_x_url = "x.com" in req.url.lower() or "twitter.com" in req.url.lower()
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
                            
                            payload["target_profile"].update({
                                "username": "@" + ig_data.username,
                                "bio": ig_data.biography or "",
                                "posts": [p.caption for p in ig_data.posts if p.caption] or [f"Instagram Profili: {ig_data.full_name or ig_data.username}"],
                                "images": [p.display_url for p in ig_data.posts],
                                "followers": ig_data.follower_count or 0,
                                "is_private": ig_data.is_private
                            })
                            
                        elif effective_type == "x" and scrape_readonly:
                            data = await asyncio.to_thread(scrape_readonly, req.url, cookies=cookie)
                            payload["target_profile"].update({k: v for k, v in data.items() if v})

                        elif effective_type == "cross" and InstagramGhostScraper:
                            # Try Instagram first
                            ctx = await browser.new_context(**ctx_kwargs)
                            page = await ctx.new_page()
                            if stealth_engine:
                                await stealth_engine.apply_stealth_async(page)
                            ig_scraper = InstagramGhostScraper(vault_cookies={"sessionid": cookie} if cookie else None)
                            try:
                                ig_data = await ig_scraper.scrape_async(clean_username, playwright_page=page)
                                payload["target_profile"].update({
                                    "username": "@" + ig_data.username,
                                    "bio": ig_data.biography or "",
                                    "posts": [p.caption for p in ig_data.posts if p.caption] or [f"Instagram: {ig_data.full_name or ig_data.username}"],
                                    "images": [p.display_url for p in ig_data.posts],
                                    "followers": ig_data.follower_count or 0,
                                    "is_private": ig_data.is_private
                                })
                            except Exception as ig_err:
                                if scrape_readonly and is_x_url:
                                    x_data = await asyncio.to_thread(scrape_readonly, req.url, cookies=cookie)
                                    payload["target_profile"].update({k: v for k, v in x_data.items() if v})
                                else:
                                    raise ig_err
                                
                        elif scrape_readonly:
                            data = await asyncio.to_thread(scrape_readonly, req.url, cookies=cookie)
                            payload["target_profile"].update({k: v for k, v in data.items() if v})
                    finally:
                        if page:
                            try: await page.close()
                            except: pass
                        if ctx:
                            try: await ctx.close()
                            except: pass
                        if browser:
                            try: await browser.close()
                            except: pass
                        
                broadcast_log(client_id, "INFO", "TELEMETRİ: Veri ele geçirildi.")
            except Exception as e:
                broadcast_log(client_id, "ERROR", f"UPLINK KOPTU: {str(e)[:100]}")
                if "InsufficientEvidenceError" in type(e).__name__ or "TargetPrivateError" in type(e).__name__:
                    raise e
        
        task_id = f"op_{datetime.now().strftime('%H%M%S')}"
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
        "follower_audit": _dump_field(getattr(res, "follower_audit", None)),
        "timing_forensics": _dump_field(getattr(res, "timing_forensics", None)),
        "depth_report": _dump_field(getattr(res, "depth_report", None)),
        "visual_evidence": _dump_field(getattr(res, "visual_evidence", None))
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
    return {
        "core": True,
        "gateway": getattr(executor.llm_gateway, 'api_key', None) is not None,
        "scraper": scrape_readonly is not None,
        "vault": "x_cookie" in vault or bool(vault.get("or_key")),
        "search_engine": bool(vault.get("search_keys", False)) or bool(getattr(executor.search_engine, 'tavily_key', None))
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

class IntervenePayload(BaseModel):
    client_id: str
    action_type: str
    target_agent: Optional[str] = None
    parameters: dict = {}

@app.post("/api/executor/intervene")
async def executor_intervene(req: IntervenePayload):
    """Kullanıcının doğrudan müdahale komutunu PinealExecutor üzerinde çalıştırır"""
    room = get_room(req.client_id)
    executor = room.get("executor")
    
    if req.action_type == "OVERRIDE_CONFIDENCE":
        executor.uncertainty.evaluate = lambda result, agent_name: type('UncertaintyResult', (), {'confidence': 1.0, 'is_suspicious': False, 'reason': 'Mösyö müdahalesi ile esnetildi'})()
        broadcast_log(req.client_id, "WARNING", "MÜDAHALE: Güven kısıtlaması kaldırıldı (Override).")
        return {"status": "overridden", "message": "Güven eşiği Mösyö emriyle 1.0'e sabitlendi."}
        
    elif req.action_type == "SKIP_AGENT" and req.target_agent:
        if req.target_agent in executor.agents:
            del executor.agents[req.target_agent]
            broadcast_log(req.client_id, "WARNING", f"MÜDAHALE: Ajan devre dışı bırakıldı [{req.target_agent}].")
            return {"status": "skipped", "message": f"{req.target_agent} ajan devre dışı."}

    elif req.action_type == "HALT":
        broadcast_log(req.client_id, "ERROR", "MÜDAHALE: Operasyon Mösyö emriyle DURDURULDU.")
        return {"status": "halted", "message": "Operasyon durduruldu."}

    return {"status": "acknowledged", "message": "Müdahale emri alındı."}

class InterpreterPayload(BaseModel):
    client_id: str
    prompt: str
    auto_run: bool = False

@app.post("/api/experimental/interpreter/execute")
async def interpreter_execute(req: InterpreterPayload):
    """Open Interpreter ile otonom kod icra eder"""
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
