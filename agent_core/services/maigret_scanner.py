"""Maigret entegrasyonu — kullanıcı adı varlık taraması (FAZ 2).

Sözleşme (projenin dürüstlük ilkeleriyle hizalı):
- Kütüphane yok / DB yok / kapalı / timeout / tüm sağlayıcı hatalı: mümkün olan
  en doğru sonucu döner (`available=False` + makine-okunur sebep). ASLA uydurma
  site/hesap üretmez.
- "Hiç iz yok" yalnızca tarama TAMAMLANIP sıfır hata ile sıfır eşleşme
  çıkarsa iddia edilir (güvenilir yokluk); karışık/failed koşularda asla.
- Kapı: ENABLE_MAIGRET=true olmadan tarayıcı ÇALIŞMAZ (default: devre dışı;
  pipeline davranışı değişmez). Limit/timeout env ile sınırlıdır.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

DEFAULT_SITES_LIMIT = 100
DEFAULT_SITE_TIMEOUT = 15
DEFAULT_TOTAL_TIMEOUT = 45
MAX_SITES_LIMIT = 500
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_SILENT_LOGGER = logging.getLogger("maigret.silent")
_SILENT_LOGGER.addHandler(logging.NullHandler())
_SILENT_LOGGER.setLevel(logging.CRITICAL)

_db_singleton: Optional[object] = None
_db_lock = threading.Lock()


class MaigretSiteHit(BaseModel):
    site: str
    url: str
    status: str = "claimed"
    model_config = ConfigDict(extra="forbid")


class MaigretScanResult(BaseModel):
    requested_username: str
    available: bool = False
    provider: str = "maigret"
    reason: Optional[str] = None
    found_sites: List[MaigretSiteHit] = []
    scanned_count: int = 0
    error_count: int = 0
    model_config = ConfigDict(extra="forbid")


def _env_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def is_enabled() -> bool:
    return os.getenv("ENABLE_MAIGRET", "false").lower() == "true"


def sanitize_username(username: str) -> Optional[str]:
    """'@Ad.Soyad' -> 'Ad.Soyad'; geçersiz karakter -> None."""
    cleaned = (username or "").strip().lstrip("@").strip()
    if not cleaned or not USERNAME_RE.match(cleaned):
        return None
    return cleaned


def _load_site_dict(top: int) -> Dict[str, object]:
    """Paket içi maigret DB'sinden (3302 site) rank'e göre top-N site seçer.

    Yalnız yükleyici; singleton + kilit `_get_site_dict`'tedir (testler
    yükleyiciyi değiştirebilir, kilit anlamlı kalır).
    """
    import pathlib

    import maigret
    from maigret.sites import MaigretDatabase

    db_path = pathlib.Path(maigret.__file__).parent / "resources" / "data.json"
    db = MaigretDatabase().load_from_file(str(db_path))
    if not db.sites_dict:
        raise RuntimeError("maigret db empty")
    return db


def _get_site_dict(top: int) -> Dict[str, object]:
    """[SAĞLAMLAŞTIRMA] Kilitli singleton: eşzamanlı taramalar 3302 sitelik
    DB'yi aynı anda iki kez yükseltemez (FAZ 2 kusuru; regresyon testi var)."""
    global _db_singleton
    with _db_lock:
        if _db_singleton is None:
            _db_singleton = _load_site_dict(top)
        db = _db_singleton
    ranked = getattr(db, "ranked_sites_dict", None)
    if ranked is None:  # test/çağıran doğrudan dict sağladı — olduğu gibi kullan
        return db  # type: ignore[return-value]
    return ranked(top=top)  # type: ignore[misc]


async def _run_library_scan(
    username: str, site_dict: Dict[str, object], timeout: int
):
    from maigret.maigret import maigret as maigret_fn

    return await maigret_fn(
        username,
        site_dict,
        _SILENT_LOGGER,
        timeout=timeout,
        no_progressbar=True,
        max_connections=min(50, max(5, len(site_dict))),
        is_parsing_enabled=False,
        retries=0,
    )


async def scan_username(
    username: str,
    limit: Optional[int] = None,
    site_timeout: Optional[int] = None,
) -> MaigretScanResult:
    """Kullanıcı adını maigret DB'sindeki (limit) sitede tarar.

    Dürüst sonuç: kapalıysa 'disabled', kütüphane yoksa 'library_missing',
    zaman aşımında 'timeout', tüm siteler hatalıysa 'provider_errors'.
    """
    if not is_enabled():
        return MaigretScanResult(requested_username=username, available=False,
                                 reason="disabled")

    clean = sanitize_username(username)
    if clean is None:
        return MaigretScanResult(requested_username=username, available=False,
                                 reason="invalid_username")

    top = _env_int("MAIGRET_SITES_LIMIT", DEFAULT_SITES_LIMIT, MAX_SITES_LIMIT)
    if limit is not None:
        top = max(1, min(int(limit), MAX_SITES_LIMIT))
    timeout = site_timeout or _env_int("MAIGRET_TIMEOUT", DEFAULT_SITE_TIMEOUT, 60)
    total_timeout = _env_int("MAIGRET_TOTAL_TIMEOUT", DEFAULT_TOTAL_TIMEOUT, 180)

    try:
        site_dict = await asyncio.to_thread(_get_site_dict, top)
    except ImportError:
        return MaigretScanResult(requested_username=clean, available=False,
                                 reason="library_missing")
    except Exception as exc:
        logger.warning("maigret db yüklenemedi: %s: %s", type(exc).__name__, str(exc)[:80])
        return MaigretScanResult(requested_username=clean, available=False,
                                 reason="db_unavailable")

    try:
        results = await asyncio.wait_for(
            _run_library_scan(clean, site_dict, timeout), timeout=total_timeout
        )
    except asyncio.TimeoutError:
        return MaigretScanResult(requested_username=clean, available=False,
                                 reason="timeout", scanned_count=len(site_dict))
    except ImportError:
        return MaigretScanResult(requested_username=clean, available=False,
                                 reason="library_missing")
    except Exception as exc:
        logger.warning("maigret tarama hatası: %s: %s", type(exc).__name__, str(exc)[:80])
        return MaigretScanResult(requested_username=clean, available=False,
                                 reason="scan_error", scanned_count=len(site_dict))

    from maigret.result import MaigretCheckStatus

    found: List[MaigretSiteHit] = []
    error_count = 0
    scanned = 0
    for site_name, result in (results or {}).items():
        scanned += 1
        status = getattr(result, "status", None)
        if status == MaigretCheckStatus.CLAIMED:
            url = getattr(result, "url_user", "") or ""
            found.append(MaigretSiteHit(site=str(site_name), url=url, status="claimed"))
        elif status in (MaigretCheckStatus.UNKNOWN, None):
            # None = denetleyici future'ı istisna ile öldü (ağ/DNS) → HATA.
            # Dürüstlük kuralı: doğrulanmamış site asla 'temiz yokluk' sayılmaz.
            error_count += 1
        # AVAILABLE (boş) ve ILLEGAL (geçersiz) sayılmaz: eşleşme değildir.

    found.sort(key=lambda h: h.site.lower())
    if found:
        available = True
        reason = "provider_errors_partial" if error_count else None
    elif scanned > 0 and error_count == 0:
        # Güvenilir yokluk: tüm siteler net yanıt verdi, hiç iz yok.
        available = True
        reason = None
    else:
        available = False
        reason = "provider_errors"

    return MaigretScanResult(
        requested_username=clean,
        available=available,
        reason=reason,
        found_sites=found,
        scanned_count=scanned,
        error_count=error_count,
    )
