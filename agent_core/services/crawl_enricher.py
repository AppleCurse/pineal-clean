"""Crawl4AI entegrasyonu — public-web sayfadan LLM-dostu metin (FAZ 4).

Sözleşme (projenin dürüstlük ilkeleriyle hizalı):
- Kapalı / kütüphane yok / tarayıcı binary'si yok / ağ yok / zaman aşımı:
  `available=False` + makine-okunur sebep. ASLA uydurma içerik üretmez.
- Tüm URL'ler `agent_core.utils.security.is_safe_url` SSRF guard'ından geçer
  (socid_enricher ile aynı kural).
- Metin yalnız gerçek çekilen sayfadan gelir; uzunluk env ile sınırlıdır.

Lisans: crawl4ai Apache-2.0 (PyPI metadata doğrulandı). Renderer:
- `http` (default): AsyncHTTPCrawlerStrategy — tarayıcı binary'si GEREKMEZ,
  düz HTTP sayfaları için yeterli (sandbox'ta da çalışabilir).
- `browser`: Playwright stratejisi — JS-heavy sayfalar; binary yoksa dürüst
  `browser_missing` döner (binary indirme bu ortamda CDN kısıtı nedeniyle
  denenmez).

psutil notu: crawl4ai `psutil>=6.1.1` beyan eder; open-interpreter
`psutil<6.0.0` beyan eder. Gerçek kullanım (kaynak okuması + çalışma zamanı
kanıtı, psutil 5.9.8): crawl4ai `Process()/process_iter()`, open-interpreter
`virtual_memory()/disk_usage()` — hepsi stabil API, 5.9.8 ile sorunsuz.
Bu yüzden `psutil<6` sabitlenir (open-interpreter'ın beyanına saygı).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 8000
MAX_MAX_CHARS = 50000
DEFAULT_TIMEOUT = 20
MAX_TIMEOUT = 120
DEFAULT_RESEARCH_LIMIT = 2
MAX_RESEARCH_LIMIT = 5

_BROWSER_MISSING_MARKERS = (
    "executable doesn't exist",
    "playwright install",
    "looks like playwright",
    "browserType.launch",
)


class CrawlFetchResult(BaseModel):
    requested_url: str
    available: bool = False
    provider: str = "crawl4ai"
    reason: Optional[str] = None
    url: str = ""                       # crawler'ın raporladığı nihai URL
    title: str = ""
    markdown: str = ""                  # LLM-dostu metin (env ile kırpılır)
    status_code: Optional[int] = None
    error_detail: Optional[str] = None  # insan-notu; makine sebep `reason`
    model_config = ConfigDict(extra="forbid")


def _env_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def is_enabled() -> bool:
    return os.getenv("ENABLE_CRAWL4AI", "false").lower() == "true"


def research_limit() -> int:
    """_run_public_web_research içinde kaç eşleşen sonucun çekileceği."""
    return _env_int("CRAWL4AI_RESEARCH_LIMIT", DEFAULT_RESEARCH_LIMIT,
                    MAX_RESEARCH_LIMIT)


def _classify_error(message: str) -> str:
    low = (message or "").lower()
    if any(marker in low for marker in _BROWSER_MISSING_MARKERS):
        return "browser_missing"
    return "fetch_error"


async def _crawl_once(url: str, renderer: str, timeout: int) -> Tuple[bool, str, str, str, Optional[int], str]:
    """crawl4ai ile tek URL çeker. Döner: (success, url, title, markdown, status_code, error_message).

    Test dikişi: bu fonksiyon monkeypatch ile değiştirilebilir; servisin geri
    kalanı sözleşmeyi buradan bağımsız doğrular.
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,       # dürüst taze çekim; önbellek yanılsaması yok
        page_timeout=timeout * 1000,
        verbose=False,
    )
    if renderer == "browser":
        strategy = None  # default Playwright stratejisi (binary ister)
        browser_cfg = BrowserConfig(headless=True)
        crawler_cm = AsyncWebCrawler(config=browser_cfg)
    else:
        from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
        strategy = AsyncHTTPCrawlerStrategy()
        crawler_cm = AsyncWebCrawler(crawler_strategy=strategy)

    async with crawler_cm as crawler:
        result = await crawler.arun(url=url, config=run_cfg)

    md = getattr(result, "markdown", "")
    text = getattr(md, "raw_markdown", None) or (md if isinstance(md, str) else "")
    title = ""
    meta = getattr(result, "metadata", None)
    if isinstance(meta, dict):
        title = str(meta.get("title") or "")
    return (
        bool(getattr(result, "success", False)),
        str(getattr(result, "url", "") or ""),
        title,
        text or "",
        getattr(result, "status_code", None),
        str(getattr(result, "error_message", "") or ""),
    )


async def fetch_readable(url: str) -> CrawlFetchResult:
    """Public-web sayfasını çekip LLM-dostu (kırpılmış) metne çevirir.

    Dürüst sonuç: kapalıysa 'disabled', URL kötüyse 'invalid_url',
    SSRF engelse 'ssrf_blocked', kütüphane yoksa 'library_missing',
    tarayıcı binary'si yoksa 'browser_missing', zaman aşımında 'timeout'.
    """
    if not is_enabled():
        return CrawlFetchResult(requested_url=url, available=False, reason="disabled")

    clean = (url or "").strip()
    if not clean.startswith(("http://", "https://")):
        return CrawlFetchResult(requested_url=url, available=False, reason="invalid_url")

    from agent_core.utils.security import is_safe_url
    if not is_safe_url(clean):
        return CrawlFetchResult(requested_url=clean, available=False, reason="ssrf_blocked")

    renderer = os.getenv("CRAWL4AI_RENDERER", "http").lower()
    if renderer not in ("http", "browser"):
        renderer = "http"
    max_chars = _env_int("CRAWL4AI_MAX_CHARS", DEFAULT_MAX_CHARS, MAX_MAX_CHARS)
    timeout = _env_int("CRAWL4AI_TIMEOUT", DEFAULT_TIMEOUT, MAX_TIMEOUT)

    try:
        success, final_url, title, text, status_code, error_message = (
            await asyncio.wait_for(
                _crawl_once(clean, renderer, timeout), timeout=timeout + 15.0
            )
        )
    except asyncio.TimeoutError:
        return CrawlFetchResult(requested_url=clean, available=False, reason="timeout")
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] == "crawl4ai":
            return CrawlFetchResult(requested_url=clean, available=False,
                                    reason="library_missing")
        return CrawlFetchResult(
            requested_url=clean,
            available=False,
            reason="dependency_broken",
            error_detail=f"{type(exc).__name__}: {str(exc)[:180]}",
        )
    except ImportError as exc:
        return CrawlFetchResult(
            requested_url=clean,
            available=False,
            reason="dependency_broken",
            error_detail=f"{type(exc).__name__}: {str(exc)[:180]}",
        )
    except Exception as exc:
        reason = _classify_error(str(exc))
        return CrawlFetchResult(requested_url=clean, available=False, reason=reason,
                                error_detail=f"{type(exc).__name__}: {str(exc)[:180]}")

    if not success:
        return CrawlFetchResult(
            requested_url=clean, available=False,
            reason=_classify_error(error_message),
            url=final_url, status_code=status_code,
            error_detail=(error_message or "")[:180] or None,
        )

    return CrawlFetchResult(
        requested_url=clean,
        available=True,
        url=final_url or clean,
        title=title,
        markdown=(text or "")[:max_chars],
        status_code=status_code,
    )
