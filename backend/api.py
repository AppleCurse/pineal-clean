from fastapi import FastAPI, WebSocket, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import os
import hashlib
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
    from agent_core.scraper.instagram_ghost import InstagramGhostScraper, InsufficientEvidenceError
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

app = FastAPI(title="PINEAL-HERETIC v2.0 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        api_key = vault.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        if api_key and not api_key.startswith("sk-or-v1-YOUR"):
            executor.llm_gateway.set_key(api_key)
            if shadow_executor is not None:
                shadow_executor.llm_gateway.set_key(api_key)
            if dialogue_manager is not None:
                dialogue_manager.llm.set_key(api_key)
            vault["or_key"] = True
            vault["api_key"] = api_key

        tavily = vault.get("tavily_key") or os.getenv("TAVILY_API_KEY")
        serpapi = vault.get("serpapi_key") or os.getenv("SERPAPI_KEY")
        exa = vault.get("exa_key") or os.getenv("EXA_API_KEY")
        if tavily or serpapi or exa:
            executor.search_engine.set_keys(tavily=tavily, serpapi=serpapi, exa=exa)
        use_local = vault.get("use_local", False)
        executor.llm_gateway.use_local = use_local

        app.state.rooms[client_id] = {
            "executor": executor,
            "vault": vault,
            "websockets": set(),
            "logs": [],
            "aspasia": AspasiaChief(llm_gateway=executor.llm_gateway) if AspasiaChief else None
        }
    return app.state.rooms[client_id]

def get_executor(client_id: str) -> PinealExecutor:
    return get_room(client_id)["executor"]

def get_vault(client_id: str) -> dict:
    return get_room(client_id)["vault"]


async def broadcast_log(client_id: str, level: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    payload = json.dumps({"type": "log", "ts": ts, "level": level, "msg": msg})
    room = app.state.rooms.get(client_id)
    if not room: return
    if "logs" not in room: room["logs"] = []
    room["logs"].append(f"[{ts}] [{level}] {msg}")
    if len(room["logs"]) > 50: room["logs"].pop(0)
    ws_set = room["websockets"]
    for ws in list(ws_set):
        try:
            await ws.send_text(payload)
        except:
            ws_set.discard(ws)

def sync_log(client_id: str, level: str, msg: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_log(client_id, level, msg))
    except RuntimeError:
        pass 

async def broadcast_event(client_id: str, event: Any):
    try:
        from agent_core.schemas.telemetry import TelemetryEvent
        telemetry = TelemetryEvent(event=event)
        payload = telemetry.model_dump_json()
        room = app.state.rooms.get(client_id)
        if not room: return
        if "events" not in room: room["events"] = []
        room["events"].append(telemetry)
        ws_set = room["websockets"]
        for ws in list(ws_set):
            try:
                await ws.send_text(payload)
            except:
                ws_set.discard(ws)
    except Exception as e:
        print(f"Error broadcasting event: {e}")

def sync_event(client_id: str, event: Any):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_event(client_id, event))
    except RuntimeError:
        pass

async def broadcast_snapshot(client_id: str, snapshot: Any):
    payload = json.dumps({
        "type": "snapshot_update",
        "task_id": snapshot.task_id,
        "current_agent": snapshot.current_agent,
        "status": snapshot.status,
        "planned_agents": snapshot.planned_agents,
        "completed_agents": snapshot.completed_agents,
        "halted_reason": getattr(snapshot, "halted_reason", None),
        "resonance_score": getattr(snapshot, "resonance_score", None),
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
    room = app.state.rooms.get(client_id)
    if not room: return
    
    # Active_tasks'a yaz
    if "active_tasks" not in room:
        room["active_tasks"] = {}
    room["active_tasks"][snapshot.task_id] = snapshot
    
    ws_set = room["websockets"]
    for ws in list(ws_set):
        try:
            await ws.send_text(payload)
        except:
            ws_set.discard(ws)

def sync_snapshot(client_id: str, snapshot: Any):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_snapshot(client_id, snapshot))
    except RuntimeError:
        pass

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
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

async def run_mission(req: InitiatePayload):
    client_id = req.client_id
    executor = get_executor(client_id)
    vault = get_vault(client_id)
    
    try:
        payload = {
            "user_profile": {
                "private_rituals": [r.strip() for r in req.rituals.split(",")],
                "late_night_playlist": [req.playlist],
                "secret_envies": [e.strip() for e in req.envies.split(",")],
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
                await broadcast_log(client_id, "INFO", f"DAEMON: Rotasyondan rastgele cookie seçildi.")
                
        if req.url:
            await broadcast_log(client_id, "INFO", f"UPLINK: Hedefe sızılıyor -> {req.url} [{req.scraper_type.upper()}]")
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
                        
                        if req.scraper_type == "instagram" and InstagramGhostScraper:
                            ctx = await browser.new_context(**ctx_kwargs)
                            if cookie:
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
                            ig_data = await ig_scraper.scrape_async(req.url.strip("/").split("/")[-1], playwright_page=page)
                            
                            payload["target_profile"].update({
                                "username": "@" + ig_data.username,
                                "bio": ig_data.biography or "",
                                "posts": [p.caption for p in ig_data.posts if p.caption],
                                "images": [p.display_url for p in ig_data.posts],
                                "followers": ig_data.follower_count or 0,
                                "is_private": ig_data.is_private
                            })
                            
                        elif req.scraper_type == "cross" and scrape_readonly and InstagramGhostScraper:
                            # Scrape X (runs sync via thread)
                            x_data = await asyncio.to_thread(scrape_readonly, req.url, cookies=cookie)
                            
                            # Scrape IG
                            ctx = await browser.new_context(**ctx_kwargs)
                            if cookie:
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
                            ig_data = await ig_scraper.scrape_async(req.url.strip("/").split("/")[-1], playwright_page=page)
                            
                            merged = x_data.copy()
                            merged["posts"] = x_data.get("posts", []) + [p.caption for p in ig_data.posts if p.caption]
                            merged["images"] = x_data.get("images", []) + [p.display_url for p in ig_data.posts]
                            payload["target_profile"].update({k: v for k, v in merged.items() if v})
                            
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
                        
                await broadcast_log(client_id, "INFO", f"TELEMETRİ: Veri ele geçirildi.")
            except Exception as e:
                await broadcast_log(client_id, "ERROR", f"UPLINK KOPTU: {str(e)[:100]}")
                if "InsufficientEvidenceError" in type(e).__name__ or "TargetPrivateError" in type(e).__name__:
                    raise e
        
        task_id = f"op_{datetime.now().strftime('%H%M%S')}"
        for attempt in range(1, 4):
            try:
                await broadcast_log(client_id, "INFO", f"OPERASYON BAŞLATILIYOR (Deneme {attempt}/3)...")
                res = await executor.execute_task(payload, task_id)
                await broadcast_result(client_id, res)
                return
            except InsufficientEvidenceError:
                raise
            except Exception as e:
                await broadcast_log(client_id, "ERROR", f"HATA: {type(e).__name__}: {str(e)[:100]}")
                if attempt == 3:
                    await broadcast_log(client_id, "ERROR", "SİSTEM PANİĞİ: MAKSİMUM DENEME AŞILDI.")
    except InsufficientEvidenceError:
        await broadcast_result_error(client_id, "halted_evidence", "DURDURULDU: YETERSİZ KANIT")
    except Exception as e:
        await broadcast_result_error(client_id, "failed", f"SİSTEM PANİĞİ: {str(e)}")

async def broadcast_result_error(client_id, status, msg):
    await broadcast_log(client_id, "ERROR", msg)
    data = {"type": "result", "status": status}
    room = app.state.rooms.get(client_id)
    if not room: return
    ws_set = room["websockets"]
    for ws in list(ws_set):
        try:
            await ws.send_text(json.dumps(data))
        except:
            pass

async def broadcast_result(client_id, res):
    def find(chain, name):
        for e in chain:
            if e["agent"] == name:
                return e["result"]
        return None
        
    data = {
        "type": "result",
        "status": res.status,
        "mirror": find(res.evidence_chain, "mirror_truth"),
        "reading": find(res.evidence_chain, "human_behavior"),
        "reso": find(res.evidence_chain, "resonance_calc"),
        "hook": find(res.evidence_chain, "pattern_interrupt")
    }
    room = app.state.rooms.get(client_id)
    if not room: return
    ws_set = room["websockets"]
    for ws in list(ws_set):
        try:
            await ws.send_text(json.dumps(data))
        except:
            pass

@app.post("/api/initiate")
async def api_initiate(req: InitiatePayload, background_tasks: BackgroundTasks):
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
        await broadcast_log(req.client_id, "INFO", f"KASA: Cookie belleğe mühürlendi.")
    if req.api_key:
        executor.llm_gateway.set_key(req.api_key)
        if shadow_executor is not None:
            shadow_executor.llm_gateway.set_key(req.api_key)
        if dialogue_manager is not None:
            dialogue_manager.llm.set_key(req.api_key)
        vault["or_key"] = True
        await broadcast_log(req.client_id, "INFO", "KASA: API Anahtarı girildi. Ağ geçidi aktif.")
        
    if req.local_url or req.local_model or req.use_local:
        executor.llm_gateway.set_local_config(
            base_url=req.local_url or None,
            model_name=req.local_model or None,
            active=req.use_local
        )
        vault["use_local"] = req.use_local
        await broadcast_log(req.client_id, "INFO", f"KASA: Yerel Kısıtlamasız LLM Yapılandırıldı ({req.local_model or 'Ollama/LM Studio'}).")

    if req.tavily_key or req.serpapi_key or req.exa_key:
        executor.search_engine.set_keys(tavily=req.tavily_key, serpapi=req.serpapi_key, exa=req.exa_key)
        vault["search_keys"] = True
        await broadcast_log(req.client_id, "INFO", "KASA: Arama Motoru anahtarları mühürlendi.")
        
    return {"status": "secured"}

class OverridePayload(BaseModel):
    client_id: str
    fact: str
    tag: str

@app.post("/api/override")
async def api_override(req: OverridePayload):
    if req.fact.strip():
        executor = get_executor(req.client_id)
        mem_dir = executor.memory.storage_path
        lp = os.path.join(mem_dir, "learnings.json")
        learn = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else []
        learn.append({"fact": req.fact.strip(), "tag": req.tag.strip(), "ts": datetime.now().isoformat(), "hash": hashlib.sha256(req.fact.strip().encode()).hexdigest()[:12]})
        with open(lp, "w", encoding="utf-8") as f:
            json.dump(learn, f, ensure_ascii=False, indent=2)
        await broadcast_log(req.client_id, "INFO", f"HAFIZA: Yeni konsept mühürlendi [{req.tag.strip()}]")
    return {"status": "sealed"}

@app.get("/api/telemetry")
async def api_telemetry(client_id: str):
    executor = get_executor(client_id)
    vault = get_vault(client_id)
    return {
        "core": True,
        "gateway": getattr(executor.llm_gateway, 'api_key', None) is not None,
        "scraper": scrape_readonly is not None,
        "vault": "x_cookie" in vault,
        "search_engine": vault.get("search_keys", False)
    }

@app.post("/api/shadow/analyze")
async def shadow_analyze(profile: dict):
    """Dark Triad analizi"""
    if shadow_executor is None:
        return {"error": "Shadow Protocol yüklü değil"}
    from agent_core.psychology.dark_triad import DarkTriadAnalyzer
    analyzer = DarkTriadAnalyzer()
    result = analyzer.analyze(profile)
    return result.model_dump()

@app.post("/api/shadow/generate")
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

@app.post("/api/chat/respond")
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
    room = get_room(payload.client_id)
    aspasia = room.get("aspasia") or aspasia_chief
    if not aspasia:
        return {"error": "Aspasia Kokpit Şefi yüklenemedi"}
    
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
        await broadcast_log(req.client_id, "WARNING", "MÜDAHALE: Güven kısıtlaması kaldırıldı (Override).")
        return {"status": "overridden", "message": "Güven eşiği Mösyö emriyle 1.0'e sabitlendi."}
        
    elif req.action_type == "SKIP_AGENT" and req.target_agent:
        if req.target_agent in executor.agents:
            del executor.agents[req.target_agent]
            await broadcast_log(req.client_id, "WARNING", f"MÜDAHALE: Ajan devre dışı bırakıldı [{req.target_agent}].")
            return {"status": "skipped", "message": f"{req.target_agent} ajan devre dışı."}

    elif req.action_type == "HALT":
        await broadcast_log(req.client_id, "ERROR", "MÜDAHALE: Operasyon Mösyö emriyle DURDURULDU.")
        return {"status": "halted", "message": "Operasyon durduruldu."}

    return {"status": "acknowledged", "message": "Müdahale emri alındı."}

class InterpreterPayload(BaseModel):
    client_id: str
    prompt: str
    auto_run: bool = False

@app.post("/api/interpreter/execute")
async def interpreter_execute(req: InterpreterPayload):
    """Open Interpreter ile otonom kod icra eder"""
    room = get_room(req.client_id)
    executor = room.get("executor")
    interpreter_agent = executor.agents.get("interpreter")
    
    if not interpreter_agent:
        return {"error": "Interpreter Agent aktif değil"}
        
    await broadcast_log(req.client_id, "INFO", f"INTERPRETER: Görev icra ediliyor -> {req.prompt[:60]}...")
    res = await interpreter_agent.execute_task(
        prompt=req.prompt,
        api_key=executor.llm_gateway.api_key,
        auto_run=req.auto_run
    )
    
    if res.status == "success":
        await broadcast_log(req.client_id, "INFO", "INTERPRETER: İcra başarıyla tamamlandı.")
    else:
        await broadcast_log(req.client_id, "ERROR", f"INTERPRETER HATA: {res.error_message}")
        
    return res.model_dump()

static_dir = "frontend/dist" if os.path.exists("frontend/dist") else "frontend"
os.makedirs(static_dir, exist_ok=True)
# Sona ekliyoruz ki api rotaları statik dosyalardan önce ezilmesin
app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
