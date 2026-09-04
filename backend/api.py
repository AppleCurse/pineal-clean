from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from collections import deque
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
from agent_core.aspasia.interface import AspasiaCommandGateway
from agent_core.chat.dialogue_manager import DialogueManager
from agent_core.scraper.instagram_ghost import InstagramGhostScraper
from agent_core.services import crawl_enricher, socid_enricher
from agent_core.services.dependency_health import (
    StartupDependencyError,
    check_startup_dependencies,
)
from agent_core.schemas.telemetry import ErrorHaltEvent, Severity, TaskCancelledEvent
from agent_core.services.routed_chat import (
    RoutingRuntimeError,
    llm_backend_mode_from_env,
    routing_runtime_from_env,
)
from agent_core.services.runtime_status import rust_core_status
from agent_core.services.task_lifecycle import TaskLifecycleRegistry
from agent_core.services.token_optimizer import OptimizationPolicy, TokenOptimizer
from agent_core.services.unified_router import RoutingStrategy
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
_tool_output_optimizer = TokenOptimizer()

@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        startup_health = check_startup_dependencies()
        startup_health["security"] = security_posture()
        application.state.llm_backend_mode = llm_backend_mode_from_env()
        application.state.openai_router = routing_runtime_from_env()
        router_fallback_active = False
        if (
            application.state.llm_backend_mode == "unified"
            and application.state.openai_router is None
        ):
            logger.error("PINEAL_ROUTER_CONFIG is missing or invalid. Falling back to legacy LLM backend, marking health as DEGRADED.")
            application.state.llm_backend_mode = "legacy"
            router_fallback_active = True
        degraded_reasons: list[str] = []
        if router_fallback_active:
            degraded_reasons.append("UNIFIED_ROUTER_CONFIG_MISSING")

        # Production'da harcama tavanı sıfırsa uyarı yüzey
        _is_prod = os.getenv("PINEAL_ENV", "development").strip().lower() in {"production", "prod"}
        try:
            _spend_cap = float(os.getenv("OPENROUTER_MAX_SPEND_USD", "0").strip())
        except ValueError:
            _spend_cap = 0.0
        _spend_unlimited = (_spend_cap == 0.0)
        if _is_prod and _spend_unlimited:
            logger.warning(
                "SPEND_CAP_UNLIMITED: OPENROUTER_MAX_SPEND_USD=0 in production "
                "allows unbounded LLM spending. Set a non-zero cap."
            )
            degraded_reasons.append("SPEND_CAP_UNLIMITED")

        startup_health["spend_cap_usd"] = None if _spend_unlimited else _spend_cap
        startup_health["spend_cap_unlimited"] = _spend_unlimited

        if degraded_reasons:
            startup_health["status"] = "degraded"
            startup_health["degraded_reasons"] = degraded_reasons

        startup_health["components"] = {
            "rust_core": rust_core_status(),
            "llm_router": {
                "backend_mode": application.state.llm_backend_mode,
                "configured": application.state.openai_router is not None,
                "active": application.state.llm_backend_mode == "unified",
                "model_groups": (
                    sorted(application.state.openai_router.model_groups)
                    if application.state.openai_router is not None
                    else []
                ),
            },
        }
        application.state.startup_health = startup_health
    except (StartupDependencyError, SecurityConfigurationError) as exc:
        application.state.startup_health = exc.as_dict()
        logger.critical("Startup security/dependency gate failed: %s", exc.error_code)
        raise

    yield
    # Kapanista odalari TEK bir yoldan kapat (temiz kapanis). [AUDIT P0-4]
    # _close_room hem sender hem gorev task'lerini iptal eder; boylece
    # calisma zamanindaki eviction ile kapanis ayni sozlesmeyi paylasir.
    for client_id in list(application.state.rooms):
        room = application.state.rooms.get(client_id)
        if room is not None:
            _close_room(client_id, room)
    application.state.rooms.clear()
    _rooms_last_seen.clear()

app = FastAPI(title="PINEAL-HERETIC v3.0.0-rc.1 API", lifespan=lifespan)
app.state.llm_backend_mode = "legacy"
app.state.openai_router = None
app.state.startup_health = {
    "status": "starting",
    "error_code": None,
    "dependencies": [],
    "components": {"rust_core": rust_core_status()},
}


@app.get("/health")
async def health():
    health_status = app.state.startup_health
    status = health_status.get("status")
    # "failed" → 503 (bağımlılık eksik veya security gate açılmamış)
    # "degraded" → 200 (servis çalışıyor ama kısmi; load-balancer geçirir,
    #   monitoring aracı degraded_reasons / error_code ile alarm üretir)
    # "ready" → 200
    # diğer (starting, None) → 503
    if status == "failed":
        return JSONResponse(health_status, status_code=503)
    if status in ("ready", "degraded"):
        return JSONResponse(health_status, status_code=200)
    return JSONResponse(health_status, status_code=503)


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
    allow_headers=[
        "Content-Type",
        "X-API-Key",
        "Authorization",
        "X-Pineal-Tool-Optimization",
        "X-Pineal-Routing-Strategy",
    ],
    expose_headers=[
        "X-Pineal-Call-ID",
        "X-Pineal-Call-IDs",
        "X-Pineal-Route-ID",
        "X-Pineal-Route-Mode",
        "X-Pineal-Routing-Strategy",
        "X-Pineal-Optimization-Mode",
        "X-Pineal-Optimization-Bytes-Saved",
        "X-Pineal-Optimization-Lossy",
    ],
)

# --- Auth (FAZ 3): PINEAL_TOKEN tanimliysa /api/* ve OpenAI uyumlu /v1/*
# kimlik doğrulaması ister. /v1 ayrıca standart Authorization: Bearer biçimini
# kabul eder; bu anahtar hiçbir zaman upstream provider anahtarı olarak kullanılmaz. ---
def _openai_error(message: str, error_type: str, code: str, param: Optional[str] = None) -> dict:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    is_api = request.url.path.startswith("/api/")
    is_openai = request.url.path.startswith("/v1/")
    if (is_api or is_openai) and request.method != "OPTIONS":
        try:
            posture = security_posture()
        except SecurityConfigurationError as exc:
            body = (
                _openai_error(
                    "Secure startup configuration required",
                    "server_error",
                    exc.error_code,
                )
                if is_openai
                else {"error": {"code": exc.error_code, "message": "Secure startup configuration required"}}
            )
            return JSONResponse(body, status_code=503)

        presented_token = request.headers.get("x-api-key")
        if is_openai:
            authorization = request.headers.get("authorization", "")
            scheme, separator, bearer = authorization.partition(" ")
            if separator and scheme.lower() == "bearer" and bearer:
                presented_token = bearer
        if posture["auth_required"] and not token_matches(presented_token):
            body = (
                _openai_error(
                    "Invalid or missing API key",
                    "authentication_error",
                    "invalid_api_key",
                )
                if is_openai
                else {"error": {"code": "UNAUTHORIZED", "message": "X-API-Key gerekli veya hatalı"}}
            )
            return JSONResponse(body, status_code=401)

        identity = presented_token or (request.client.host if request.client else "unknown")
        identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        # [AUDIT P1-18a] Hız sınırı kimliği SUNUCUDAN türetilir ve handler'lara
        # buradan aktarılır. Eskiden handler'lar istemcinin gönderdiği
        # client_id'yi anahtar olarak kullanıyordu; client_id her istekte
        # değiştirilince sınır hiç devreye girmiyordu (ölçülen: 200/200 geçti).
        request.state.rate_identity = identity_hash
        if request.url.path.startswith("/api/experimental/"):
            if not rate_limit(f"experimental:{identity_hash}", "experimental"):
                return JSONResponse(
                    {"error": {"code": "RATE_LIMITED", "message": "Experimental endpoint rate limit exceeded"}},
                    status_code=429,
                )
        elif is_openai and not rate_limit(f"openai:{identity_hash}", "openai"):
            return JSONResponse(
                _openai_error(
                    "OpenAI-compatible endpoint rate limit exceeded",
                    "rate_limit_error",
                    "rate_limit_exceeded",
                ),
                status_code=429,
            )
        # [AUDIT P1-18b] Genel kova yalnızca MUTASYON yöntemlerine uygulanır.
        # Tek kova tüm yöntemleri paylaşsaydı ucuz GET'ler (telemetri, görev
        # listesi) mutasyonlar için gereken bütçeyi tüketiyordu — ölçülen:
        # 305 GET sonrası aynı kimlik POST'larında erken 429.
        if (
            is_api
            and request.method not in ("GET", "HEAD", "OPTIONS")
            and not rate_limit(f"api:{identity_hash}", "api")
        ):
            return JSONResponse(
                {"error": {"code": "RATE_LIMITED", "message": "API rate limit exceeded"}},
                status_code=429,
            )
    return await call_next(request)


# --- Tutarli hata modeli (FAZ 3) ---
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    body = (
        _openai_error(str(exc.detail), "invalid_request_error", str(exc.status_code))
        if request.url.path.startswith("/v1/")
        else {"error": {"code": str(exc.status_code), "message": str(exc.detail)}}
    )
    return JSONResponse(body, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith("/v1/"):
        return await request_validation_exception_handler(request, exc)
    first_error = exc.errors()[0] if exc.errors() else {}
    location = first_error.get("loc", ())
    param = ".".join(str(part) for part in location if part != "body") or None
    return JSONResponse(
        _openai_error(
            "Invalid chat completion request",
            "invalid_request_error",
            "validation_error",
            param,
        ),
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    body = (
        _openai_error("Internal server error", "server_error", "internal_error")
        if request.url.path.startswith("/v1/")
        else {"error": {"code": "INTERNAL", "message": type(exc).__name__}}
    )
    return JSONResponse(body, status_code=500)


# --- Basit kayan-pencere rate limit (FAZ 3; ek bagimlilik yok) ---
RATE_LIMITS = {
    # [AUDIT P1-18b] Genel /api/ arka plan kovası. Eskiden /api/vault,
    # /api/override, /api/executor/intervene, /api/tasks*, /api/telemetry,
    # /api/aspasia/state ve /api/scraper/authorize-alternative uçlarında HİÇ
    # hız sınırı yoktu. 300/60sn ölçülerek seçildi: frontend'de polling yok
    # (setInterval sıfır), CI smoke en kötü 30 telemetri isteği atıyor.
    "api": (300, 60),
    "initiate": (5, 60),
    "aspasia": (20, 60),
    "experimental": (10, 60),
    "openai": (60, 60),
}  # (request count, window seconds)
class _RateBucket:
    """Kayan pencere olayları + BU kovaya ait pencere süresi.

    [AUDIT P0-5 v3] Pencere kovayla birlikte saklanmak zorunda. Eskiden
    yalnızca deque tutuluyordu ve süpürme "en geniş pencere"yi (tüm
    kovaların maksimumu, 60 sn) kullanmak zorunda kalıyordu: 1 sn'lik bir
    kovadaki anahtar 60 sn boyunca bellekte kalıyordu. Ölçülen: 30.000 tekil
    anahtar, pencere dolmuş, süpürme çalışıyor -> 30.000 kova hâlâ yerinde.
    """

    __slots__ = ("events", "window")

    def __init__(self, window: float):
        self.events: deque = deque()
        self.window = window


_rate_buckets: Dict[str, _RateBucket] = {}


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


# [AUDIT P0-5] defaultdict her erişimde kalıcı bir anahtar yaratıyordu ve hiçbir
# zaman silinmiyordu (ölçülen: 5000 farklı kimlik -> 5000 kalıcı deque).
# identity ya token ya da istemci IP'si olduğundan bu, internete açık bir uçta
# durdurulamaz bir bellek sızıntısıdır. İki savunma eklendi: boşalan kova anında
# geri verilir ve anahtar sayısı sert bir tavanla sınırlanır.
_MAX_RATE_BUCKETS = _bounded_env_int("PINEAL_MAX_RATE_BUCKETS", 100_000, 1_000, 10_000_000)
# [AUDIT P0-5 v2] Süpürme artık ZAMANA da bağlı. Eskiden yalnızca tavan
# aşıldığında çalışıyordu; ölçülen iki kusur:
#   (a) 60.000 tekil anahtar -> 60.000 kalıcı kova / 50.3 MB, hepsinin penceresi
#       dolmuş ama tavana kadar HİÇBİRİ geri kazanılmıyor (P0-2'nin ikizi).
#   (b) tavan aşıldığında süpürme HER yeni istekte çalışıyor ve tüm sözlüğü
#       sorted() ile sıralıyordu -> üretim tavanında ölçülen ~48-57 ms/istek
#       (kendi kendine DoS).
_RATE_SWEEP_INTERVAL_SECONDS = max(1.0, float(
    os.getenv("PINEAL_RATE_SWEEP_INTERVAL_SECONDS", "60")
))
_rate_sweep_deadline = time.monotonic() + _RATE_SWEEP_INTERVAL_SECONDS


def _maybe_sweep_rate_buckets(now: float) -> None:
    """Süresi geldiyse süpür. Her çağrıda tek float karşılaştırması (~50 ns)."""
    global _rate_sweep_deadline
    if now >= _rate_sweep_deadline:
        # Son tarih önce yenilenir: süpürme patlasa bile her istekte yeniden
        # denenmez, maliyet tek bir isteğe yığılmaz.
        _rate_sweep_deadline = now + _RATE_SWEEP_INTERVAL_SECONDS
        _sweep_rate_buckets(now)


def _sweep_rate_buckets(now: float) -> None:
    """Süresi dolmuş kovaları geri kazanır, gerekirse tavanın altına indirir.

    Üç aşama:
      1. Kendi penceresi dolmuş veya boş kovalar silinir — bunları düşürmek
         hiçbir limiti gevşetmez. Pencere KOVADA saklandığı için ayıklama
         kova başına doğrudur (bkz. _RateBucket).
      2. Hâlâ tavandaysa EN ESKİ (LRU) kovalar düşürülür.
      3. HİSTEREZİS: tavan-1'e değil tavanın ~%80'ine inilir. Aksi halde
         süpürme her yeni istekte yeniden tetikleniyordu (ölçülen ~57 ms/istek).
    """
    for key in [
        k for k, b in _rate_buckets.items()
        if not b.events or now - b.events[-1] > b.window
    ]:
        _rate_buckets.pop(key, None)
    target = max(1, _MAX_RATE_BUCKETS - max(1, _MAX_RATE_BUCKETS // 5))
    overflow = len(_rate_buckets) - target
    if overflow > 0:
        oldest = sorted(
            _rate_buckets,
            key=lambda k: _rate_buckets[k].events[-1] if _rate_buckets[k].events else 0.0,
        )
        for key in oldest[:overflow]:
            _rate_buckets.pop(key, None)


# [AUDIT P1-18a] Kimlik yoksa TÜM kimliksiz çağıranlar tek ortak kovayı
# paylaşır. Fail-safe: "kimlik yok -> sınırsız" değil, "kimlik yok -> paylaşımlı
# ve sınırlı". Doğrudan handler çağrısı (test) da sınırsız yol bulamaz.
_UNIDENTIFIED_RATE_IDENTITY = "unidentified"


def _rate_identity(request: Request) -> str:
    """Hız sınırı için sunucudan türetilmiş kimliği döndürür.

    Handler'lar eskiden `req.client_id` kullanıyordu — bu, istemcinin gövdede
    gönderdiği bir alan. Ölçülen: aynı client_id ile 8 istek -> 3/8 429
    (sınır çalışıyor); her istekte farklı client_id -> 200 istek, 0/200 429.
    """
    identity = getattr(getattr(request, "state", None), "rate_identity", None)
    return identity or _UNIDENTIFIED_RATE_IDENTITY


def rate_limit(key: str, bucket: str) -> bool:
    """True = izin ver; False = limit asildi (429)."""
    limit, window = RATE_LIMITS.get(bucket, (999, 1))
    now = time.monotonic()
    _maybe_sweep_rate_buckets(now)
    bucket = _rate_buckets.get(key)
    if bucket is None:
        if len(_rate_buckets) >= _MAX_RATE_BUCKETS:
            _sweep_rate_buckets(now)
        bucket = _rate_buckets[key] = _RateBucket(window)
    elif bucket.window != window:
        bucket.window = window          # RATE_LIMITS çalışma zamanında değişti
    events = bucket.events
    while events and now - events[0] > window:
        events.popleft()
    if len(events) >= limit:
        return False
    # [AUDIT P0-5] Boşalan kova burada silinMEZ: izin verilen her çağrı hemen
    # aşağıdaki append ile anahtarı geri koyardı, yani silme ölü koddu
    # (mutasyon testiyle doğrulandı: satırı kaldırmak hiçbir testi kızartmadı).
    # Geri kazanımın gerçek yolları zaman temelli _maybe_sweep_rate_buckets ve
    # tavan acil-durum süpürmesidir.
    events.append(now)
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

VAULT_FILE = ".pineal_vault.json"


def _load_vault(vault_file: str = VAULT_FILE) -> dict:
    """[AUDIT P0-3] Kasayı HER ZAMAN bir dict olarak döndürür.

    Eskiden ``json.load`` bir try/except içindeydi ama sonrasındaki
    ``vault.pop(...)`` / ``vault.get(...)`` çağrıları korumasızdı. Dosya bir
    JSON dizisi/null/metin/sayı içerdiğinde (elle düzenleme, yarım kalan yazma)
    ``get_room`` TypeError/AttributeError atıyordu ve get_room HER endpoint'in
    giriş kapısı olduğu için tüm API 500 dönüyordu — üstelik sessizce, log yok.
    """
    if not os.path.exists(vault_file):
        return {}
    try:
        with open(vault_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.warning(
            "VAULT_CORRUPT: %s okunamadı (%s: %s); boş kasa ile devam ediliyor",
            vault_file, type(exc).__name__, exc,
        )
        return {}
    if not isinstance(data, dict):
        logger.error(
            "VAULT_SCHEMA_INVALID: %s bir JSON nesnesi değil (%s); yok sayıldı",
            vault_file, type(data).__name__,
        )
        return {}
    return data


# [AUDIT P0-4] Oda kayıt defteri sınırları. client_id istemcinin seçtiği,
# doğrulanmayan bir string olduğu için sınırsız oda = sınırsız PinealExecutor +
# sender task + kuyruk = OOM (ölçülen: 300 farklı client_id -> 300 kalıcı oda).
_MAX_ROOMS = _bounded_env_int("PINEAL_MAX_ROOMS", 512, 1, 1_000_000)
# Üretecin biçimi "client_<7 karakter>"; 64 geniş bir pay bırakır.
_MAX_CLIENT_ID_LENGTH = _bounded_env_int("PINEAL_MAX_CLIENT_ID_LENGTH", 64, 8, 4_096)
_ROOM_TTL_SECONDS = float(os.getenv("PINEAL_ROOM_TTL_SECONDS", "1800"))
_rooms_last_seen: Dict[str, float] = {}


class RoomCapacityExceeded(RuntimeError):
    """Eşzamanlı oda tavanı aşıldı; istemciye 503 olarak yansıtılır."""


@app.exception_handler(RoomCapacityExceeded)
async def room_capacity_handler(request: Request, exc: RoomCapacityExceeded):
    """[AUDIT P0-4] Oda tavanı bir hata değil, kasıtlı bir korumadır.

    500 değil 503 döner: istemci (ve yük dengeleyici) bunu "geçici, tekrar
    denenebilir" olarak yorumlar; 500 ile karıştırılıp alarm üretilmez.
    """
    logger.warning("ROOM_CAPACITY_EXCEEDED path=%s", request.url.path)
    body = (
        _openai_error("Server room capacity exceeded", "server_error", "room_capacity_exceeded")
        if request.url.path.startswith("/v1/")
        else {"error": {"code": "ROOM_CAPACITY_EXCEEDED", "message": str(exc)}}
    )
    return JSONResponse(body, status_code=503)


def _close_room(client_id: str, room: dict) -> None:
    """Bir odayı kapatır: sender task ve görev task'leri iptal edilir."""
    sender = room.get("sender_task")
    if sender is not None and not sender.done():
        sender.cancel()
    for mission in (room.get("mission_tasks") or {}).values():
        if not mission.done():
            mission.cancel()
    # Not: aktif WebSocket'i olan bir oda _evict_rooms tarafından zaten
    # atlanır; burada soket kapatmaya çalışmak (close() bir coroutine'dir)
    # await edilemeyeceği için yapılmaz.
    app.state.rooms.pop(client_id, None)
    _rooms_last_seen.pop(client_id, None)


def _evict_rooms(now: float) -> int:
    """Boşta kalmış odaları geri kazanır. Aktif görevi/bağlantısı olan dokunulmaz."""
    if now - getattr(_evict_rooms, "_last_sweep", 0.0) < 5.0:
        return 0
    _evict_rooms._last_sweep = now
    evicted = 0
    for client_id in list(app.state.rooms):
        room = app.state.rooms.get(client_id)
        if room is None:
            continue
        if room.get("mission_tasks") or room.get("websockets"):
            continue
        if now - _rooms_last_seen.get(client_id, now) < _ROOM_TTL_SECONDS:
            continue
        _close_room(client_id, room)
        evicted += 1
    if evicted:
        logger.info("ROOM_EVICTION: %s boşta kalmış oda kapatıldı", evicted)
    return evicted


def get_room(client_id: str) -> dict:
    # [AUDIT P0-4] client_id bir güvenlik sınırıdır: biçim VE uzunluk
    # doğrulanır. validate_identifier'ın regex'i uzunluk sınırlamadığı için
    # (^[A-Za-z0-9_-]+$) 5 KB'lık bir client_id kabul ediliyordu; her biri
    # kalıcı bir sözlük anahtarı + tam bir oda demek.
    if not client_id or len(client_id) > _MAX_CLIENT_ID_LENGTH:
        raise HTTPException(status_code=400, detail="INVALID_CLIENT_ID")
    try:
        validate_identifier(client_id, field="client_id")
    except ValueError:
        raise HTTPException(status_code=400, detail="INVALID_CLIENT_ID") from None
    now = time.monotonic()
    _evict_rooms(now)
    _rooms_last_seen[client_id] = now
    if client_id not in app.state.rooms:
        if len(app.state.rooms) >= _MAX_ROOMS:
            raise RoomCapacityExceeded(
                f"ROOM_CAPACITY_EXCEEDED: {_MAX_ROOMS} eşzamanlı oda sınırına ulaşıldı"
            )
        executor = PinealExecutor(
            log_callback=lambda lvl, msg: sync_log(client_id, lvl, msg),
            emit_event_callback=lambda evt: sync_event(client_id, evt),
            snapshot_callback=lambda s: sync_snapshot(client_id, s)
        )
        # Otomatik Kasa (.pineal_vault.json / .env) yüklemesi
        vault = _load_vault()

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
            # ASPASIA PROMOTION: ayni kisi + denetim arayuzu + tek yazma kanali.
            # Komut dispatch'i /api/initiate'in kullandigi GERCEK görev akisina
            # baglidir; ikinci bir orchestrator yoktur.
            "aspasia": (AspasiaChief(
                llm_gateway=executor.llm_gateway,
                command_gateway=AspasiaCommandGateway(
                    dispatch=_aspasia_command_dispatch,
                    gateway=executor.llm_gateway,
                ),
                executor=executor,
            ) if AspasiaChief else None),
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


class OpenAIChatCompletionPayload(BaseModel):
    """Supported, bounded subset of the OpenAI chat-completions request."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1, max_length=256)
    messages: list[dict[str, Any]] = Field(min_length=1, max_length=1024)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    max_completion_tokens: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    stop: Any = None
    tools: Optional[list[dict[str, Any]]] = Field(default=None, max_length=128)
    tool_choice: Any = None
    response_format: Optional[dict[str, Any]] = None
    seed: Optional[int] = None
    user: Optional[str] = Field(default=None, max_length=256)
    n: int = Field(default=1, ge=1, le=1)
    stream: bool = False
    stream_options: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_protocol_shape(self):
        if self.max_tokens is not None and self.max_completion_tokens is not None:
            raise ValueError("max_tokens and max_completion_tokens are mutually exclusive")
        allowed_roles = {"system", "developer", "user", "assistant", "tool", "function"}
        for message in self.messages:
            if not isinstance(message, dict) or message.get("role") not in allowed_roles:
                raise ValueError("every message requires a supported role")
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > 1_048_576:
            raise ValueError("chat completion request exceeds 1 MiB")
        return self


def _openai_gateway():
    return get_executor("openai-compatible").llm_gateway


def _tool_optimization_policy(request: Request) -> tuple[str, OptimizationPolicy]:
    requested = request.headers.get("x-pineal-tool-optimization")
    mode = (requested or os.getenv("PINEAL_TOOL_OPTIMIZATION", "disabled")).strip().lower()
    if mode in {"disabled", "off", "none"}:
        return "disabled", OptimizationPolicy()
    if mode == "safe":
        return "safe", OptimizationPolicy(enabled=True)
    if mode == "lossy":
        return "lossy", OptimizationPolicy(
            enabled=True,
            engine_ids=(
                "strip-ansi",
                "compact-json",
                "collapse-repeated-lines",
                "head-tail",
            ),
            allow_lossy=True,
        )
    raise ValueError("tool optimization mode must be disabled, safe, or lossy")


def _routing_strategy(request: Request) -> RoutingStrategy:
    requested = request.headers.get("x-pineal-routing-strategy")
    value = (requested or os.getenv("PINEAL_ROUTING_STRATEGY", "auto")).strip().lower()
    try:
        return RoutingStrategy(value)
    except ValueError as exc:
        raise ValueError("unknown Pineal routing strategy") from exc


@app.get("/v1/models")
async def openai_models():
    gateway = _openai_gateway()
    now = int(time.time())
    models: dict[str, str] = {}
    routed = app.state.openai_router
    if app.state.llm_backend_mode == "unified" and routed is not None:
        models.update({
            model_id: "pineal-router"
            for model_id in routed.executable_models(gateway)
        })
    else:
        cloud_enabled = gateway.client is not None and (
            os.getenv("LIVE_LLM_E2E") == "1" or gateway.live_unlocked
        )
        if cloud_enabled:
            models.update({model_id: "openrouter" for model_id in gateway.MODEL_PRICING})
        if gateway.use_local and gateway.local_client is not None:
            models[gateway.local_model] = "local"
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": now,
                "owned_by": owner,
            }
            for model_id, owner in sorted(models.items())
        ],
    }


def _stream_chunk_dict(chunk: Any) -> dict[str, Any]:
    if hasattr(chunk, "model_dump"):
        value = chunk.model_dump(mode="json", exclude_none=True)
    elif isinstance(chunk, dict):
        value = chunk
    else:
        raise ValueError("invalid upstream stream chunk")
    if not isinstance(value, dict):
        raise ValueError("invalid upstream stream chunk")
    return value


def _openai_streaming_response(
    routed_stream,
    *,
    call_ids: tuple[str, ...],
    optimization_mode: str,
    optimization_bytes_saved: int,
    optimization_lossy: bool,
) -> StreamingResponse:
    async def event_source():
        try:
            async for chunk in routed_stream.stream.chunks:
                data = json.dumps(
                    _stream_chunk_dict(chunk),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            error = _openai_error(
                "The selected provider stream was interrupted after output began",
                "server_error",
                "stream_interrupted",
            )
            yield "data: " + json.dumps(error, separators=(",", ":")) + "\n\n"
        yield "data: [DONE]\n\n"

    plan = routed_stream.plan
    headers = {
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        "X-Pineal-Call-ID": routed_stream.stream.call_id,
        "X-Pineal-Call-IDs": ",".join(call_ids),
        "X-Pineal-Route-ID": plan.route_id,
        "X-Pineal-Route-Mode": plan.mode.value,
        "X-Pineal-Routing-Strategy": plan.strategy.value,
        "X-Pineal-Optimization-Mode": optimization_mode,
        "X-Pineal-Optimization-Bytes-Saved": str(optimization_bytes_saved),
        "X-Pineal-Optimization-Lossy": str(optimization_lossy).lower(),
    }
    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers=headers,
    )


@app.post("/v1/chat/completions")
async def openai_chat_completions(payload: OpenAIChatCompletionPayload, request: Request):
    from agent_core.services.llm_gateway import SpendCapExceeded

    if payload.stream and app.state.llm_backend_mode != "unified":
        return JSONResponse(
            _openai_error(
                "Streaming requires PINEAL_LLM_BACKEND=unified",
                "invalid_request_error",
                "streaming_requires_unified_backend",
                "stream",
            ),
            status_code=400,
        )
    if payload.stream and payload.tools:
        return JSONResponse(
            _openai_error(
                "Streaming tool calls are not enabled",
                "invalid_request_error",
                "streaming_tools_not_supported",
                "tools",
            ),
            status_code=400,
        )

    try:
        optimization_mode, optimization_policy = _tool_optimization_policy(request)
    except ValueError as exc:
        return JSONResponse(
            _openai_error(
                str(exc),
                "invalid_request_error",
                "invalid_optimization_mode",
            ),
            status_code=400,
        )
    try:
        routing_strategy = _routing_strategy(request)
    except ValueError as exc:
        return JSONResponse(
            _openai_error(
                str(exc),
                "invalid_request_error",
                "invalid_routing_strategy",
            ),
            status_code=400,
        )
    optimized = _tool_output_optimizer.optimize(
        {"messages": payload.messages, "tools": payload.tools},
        optimization_policy,
    )
    optimized_messages = optimized.body["messages"]
    optimized_tools = optimized.body["tools"]
    lossy_applied = any(
        engine_id in {"collapse-repeated-lines", "head-tail"}
        and savings.applications > 0
        for engine_id, savings in optimized.stats.engine_savings.items()
    )

    gateway = _openai_gateway()
    routed = app.state.openai_router
    effective_max_tokens = payload.max_tokens or payload.max_completion_tokens
    route_plan = None
    call_ids: tuple[str, ...] = ()
    try:
        with gateway.capture_calls(
            task_id=_new_task_id(),
            agent_id="openai-compatible",
        ) as call_scope:
            if app.state.llm_backend_mode == "unified":
                if routed is None:
                    raise RoutingRuntimeError("unified router is not configured")
                if not routed.handles(payload.model):
                    raise RoutingRuntimeError(
                        f"unknown unified model group: {payload.model}"
                    )
                if payload.stream:
                    routed_stream = await routed.start_chat_stream(
                        gateway,
                        messages=optimized_messages,
                        model=payload.model,
                        strategy=routing_strategy,
                        temperature=payload.temperature,
                        max_tokens=effective_max_tokens,
                        top_p=payload.top_p,
                        stop=payload.stop,
                        response_format=payload.response_format,
                        seed=payload.seed,
                        user=payload.user,
                        stream_options=payload.stream_options,
                    )
                    stream_call_ids = tuple(call_scope.call_ids)
                    if routed_stream.stream.call_id not in stream_call_ids:
                        stream_call_ids += (routed_stream.stream.call_id,)
                    return _openai_streaming_response(
                        routed_stream,
                        call_ids=stream_call_ids,
                        optimization_mode=optimization_mode,
                        optimization_bytes_saved=optimized.stats.bytes_saved,
                        optimization_lossy=lossy_applied,
                    )
                routed_result = await routed.chat_completion(
                    gateway,
                    messages=optimized_messages,
                    model=payload.model,
                    strategy=routing_strategy,
                    temperature=payload.temperature,
                    max_tokens=effective_max_tokens,
                    top_p=payload.top_p,
                    stop=payload.stop,
                    tools=optimized_tools,
                    tool_choice=payload.tool_choice,
                    response_format=payload.response_format,
                    seed=payload.seed,
                    user=payload.user,
                )
                result = routed_result.result
                route_plan = routed_result.plan
            else:
                result = await gateway.chat_completion(
                    messages=optimized_messages,
                    model=payload.model,
                    temperature=payload.temperature,
                    max_tokens=effective_max_tokens,
                    top_p=payload.top_p,
                    stop=payload.stop,
                    tools=optimized_tools,
                    tool_choice=payload.tool_choice,
                    response_format=payload.response_format,
                    seed=payload.seed,
                    user=payload.user,
                )
            call_ids = tuple(call_scope.call_ids)
    except SpendCapExceeded:
        return JSONResponse(
            _openai_error(
                "Configured spend cap would be exceeded",
                "insufficient_quota",
                "spend_cap_exceeded",
            ),
            status_code=429,
        )
    except ValueError as exc:
        return JSONResponse(
            _openai_error(str(exc), "invalid_request_error", "invalid_request"),
            status_code=400,
        )
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0]
        if code.startswith("UNKNOWN_PRICING"):
            status_code = 400
            message = "Requested model has no verified pricing record"
            error_type = "invalid_request_error"
        else:
            status_code = 503
            message = "Configured LLM provider is unavailable"
            error_type = "server_error"
        return JSONResponse(
            _openai_error(message, error_type, code.lower()),
            status_code=status_code,
        )
    except Exception as exc:
        upstream_status = getattr(exc, "status_code", None)
        if upstream_status in {400, 404, 408, 413, 422, 429}:
            status_code = upstream_status
            error_type = "rate_limit_error" if upstream_status == 429 else "invalid_request_error"
        else:
            status_code = 502
            error_type = "server_error"
        return JSONResponse(
            _openai_error(
                "Upstream provider rejected the chat completion request",
                error_type,
                f"upstream_{upstream_status or 'error'}",
            ),
            status_code=status_code,
        )

    response = result.response
    if hasattr(response, "model_dump"):
        body = response.model_dump(mode="json", exclude_none=True)
    elif isinstance(response, dict):
        body = response
    else:
        return JSONResponse(
            _openai_error("Invalid upstream response", "server_error", "invalid_upstream_response"),
            status_code=502,
        )
    response_headers = {
        "Cache-Control": "no-store",
        "X-Pineal-Call-ID": result.call_id,
        "X-Pineal-Call-IDs": ",".join(call_ids),
        "X-Pineal-Optimization-Mode": optimization_mode,
        "X-Pineal-Optimization-Bytes-Saved": str(optimized.stats.bytes_saved),
        "X-Pineal-Optimization-Lossy": str(lossy_applied).lower(),
    }
    if route_plan is not None:
        response_headers.update({
            "X-Pineal-Route-ID": route_plan.route_id,
            "X-Pineal-Route-Mode": route_plan.mode.value,
            "X-Pineal-Routing-Strategy": route_plan.strategy.value,
        })
    return JSONResponse(body, headers=response_headers)


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
    except Exception:
        # [AUDIT P1-18c] Eskiden bare `except:` idi. Ölçülen: bare except
        # BaseException'ı da yakaladığı için asyncio.CancelledError yutuluyor
        # ve görev iptal edilmiş sayılmıyordu (task.cancelled() == False).
        # `except Exception:`'a geçmek tek başına YETMEZ: kontrol ölçümünde
        # iptal durumunda temizlik kayboldu. Bu yüzden temizlik finally'de.
        logger.debug("WebSocket bağlantısı koptu: %s", client_id)
    finally:
        room["websockets"].discard(websocket)

class InitiatePayload(BaseModel):
    client_id: str
    url: str
    rituals: str
    playlist: str
    envies: str
    scraper_type: str = "instagram"
    # ASPASIA TRUE CHIEF LAYER: kullanicinin AMACI (goal id'leri) görev
    # verisiyle birlikte tasinir — ama AJAN SECIMI degil; sozlesme tek
    # kaynagi CognitiveRouter.GOAL_FOCUS. Bos = eski davranis (compat).
    aspasia_goals: List[str] = []
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
            "target_profile": {"bio": "", "posts": [], "post_times": [], "images": []},
            # Amaç kaybi fix: Aspasia goal'leri payload'da yasar; router yoksa
            # eski plani aynen kurar. Gecerlilik/uydurma filtresi router'da.
            "aspasia_goals": list(req.aspasia_goals or []),
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
async def api_initiate(req: InitiatePayload, request: Request):
    if not rate_limit(f"initiate:{_rate_identity(request)}", "initiate"):
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


def _aspasia_command_dispatch(spec: dict) -> "str | None":
    """ASPASIA PROMOTION — komutların TEK yetkili yazma kanalı.

    /api/initiate ile BİREBİR aynı akış: görev kimliği _new_task_id, yaşam
    döngüsü TaskLifecycleRegistry, yürütme run_mission, takip mission_tasks.
    Kota/harcama/routing politikaları içinde bulunduğumuz gerçek gateway
    yığınındadır; bu fonksiyon hiçbir politika katmanını atlatmaz ve yeni bir
    planlama beyni kurmaz (ajan planı = executor'ın CognitiveRouter'ı).
    """
    client_id = spec["client_id"]
    room = get_room(client_id)
    req = InitiatePayload(
        client_id=client_id,
        url=spec["target_url"],
        # [009] doktrini: kullanicidan gelmeyen rituel/sarki/ozlem verisi
        # ASLA uydurulmaz — Aspasia komutu yalnizca kullaniciya ait alanlari tasir.
        rituals="",
        playlist="",
        envies="",
        # AMAÇ TAŞIMA (Phase 1): kullanici mesajindaki odak, görev verisiyle
        # birlikte CognitiveRouter'a kadar gider; burada planlama YAPILMAZ.
        aspasia_goals=list(spec.get("goals") or []),
    )
    task_id = _new_task_id()
    _lifecycle(room).transition(task_id, "processing")
    mission = asyncio.create_task(run_mission(req, task_id))
    room["mission_tasks"][task_id] = mission
    mission.add_done_callback(lambda _task: room["mission_tasks"].pop(task_id, None))
    return task_id


class AspasiaCommandPayload(BaseModel):
    client_id: str
    user_message: str


@app.post("/api/aspasia/command")
async def aspasia_command(payload: AspasiaCommandPayload, request: Request):
    """Aspasia: doğal dil niyeti -> yapılandırılmış komut -> gerçek orchestrator.

    Kabul edilen tek yazma eylemi run_profile_analysis'tir ve hedef doğrulama
    (gerçek scraper host sözleşmesi) + gateway politika yığınını aynen geçer.
    """
    if not rate_limit(f"aspasia:{_rate_identity(request)}", "aspasia"):
        return JSONResponse(
            {"error": {"code": "RATE_LIMITED", "message": "Aspasia yoğun; kısa bir mola verin."}},
            status_code=429,
        )
    room = get_room(payload.client_id)
    aspasia = room.get("aspasia") or aspasia_chief
    if not aspasia or getattr(aspasia, "commands", None) is None:
        return JSONResponse(
            {"error": {"code": "COMMANDS_UNAVAILABLE", "message": "Aspasia komut kanalı tanımlı değil"}},
            status_code=503,
        )
    result = await aspasia.commands.submit(payload.user_message, client_id=payload.client_id)
    if result.accepted and result.task_id:
        broadcast_log(payload.client_id, "INFO",
                      f"ASPASIA KOMUT [{result.command_id}] {result.intent} → görev {result.task_id}")
    return result.model_dump()


@app.get("/api/aspasia/state")
async def aspasia_state(client_id: str = "default"):
    """Read-only denetim görünümü: registry + görev durumu + bütçe + kota + anomaliler.

    Yeni bir telemetri sistemi DOĞMAZ; hepsi mevcut SoT okuyucularıdır
    (gateway call_log/budget, QuotaGovernor, executor.agents, lifecycle).
    """
    from agent_core.aspasia.interface import (
        AgentInspector,
        CostReader,
        QuotaReader,
        TelemetryReader,
    )

    room = get_room(client_id)
    executor = room.get("executor")
    gateway = executor.llm_gateway if executor is not None else aspasia_chief.llm
    inspector = AgentInspector(executor)
    return {
        "registry": inspector.registry(),
        "run": inspector.run_status(room),
        "budget": CostReader(gateway).snapshot(),
        "quota": {p: QuotaReader(gateway=gateway).snapshot(p) for p in ("groq", "cerebras")},
        "anomalies": TelemetryReader(gateway).anomalies(),
    }


@app.post("/api/aspasia/chat")
async def aspasia_chat(payload: AspasiaChatPayload, request: Request):
    """Aspasia Kokpit Şefi ile canlı Sokratik diyalog"""
    if not rate_limit(f"aspasia:{_rate_identity(request)}", "aspasia"):
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
    if os.getenv("ENABLE_INTERPRETER", "false").lower() != "true":
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
