"""Platform karar merkezi — TEK sahiplik ([023]/[049]/W4.2).

Bu modül platform routing + Instagram kazıma + glue mapping'in tek kaynağıdır:
- backend/api.py run_mission burayı kullanır
- scripts/run_task.py (Rust TaskManager'ın standart girişi) burayı kullanır

Kural ([009] duplication dersi): ikinci bir platform-karar/scraper katmanı
YARATILMAZ. Rust tarafı platform seçmez; karar burada verilir.

Sözleşme (sahte veri YASAK):
- Tanınmayan platform -> "unsupported_web"; URL segmenti Instagram adı sanılıp
  yanlış hedef kazınmaz.
- Kazıma kanıt üretemezse InsufficientEvidenceError yükselir; boş/sentetik
  profil ÜRETİLMEZ.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = ("instagram",)


def effective_scraper_type(url: str, requested: Optional[str] = None) -> str:
    """URL platformuna göre tarayıcı seç ([023] fix: platform registry).

    Instagram adresi X tarayıcısına gitmesin diye URL platform tespiti
    önceliklidir; ancak tanınmayan platformda kullanıcı seçimi GEÇERLİ
    DEĞİLDİR: URL'nin son path segmentini Instagram adı gibi kullanıp
    yanlış hedefi kazımak misattribution'dır. Tanınmayan platform ->
    unsupported_web (çağıran analizi başlatmadan durur).
    """
    u = (url or "").lower()
    if "instagram.com" in u:
        return "instagram"
    if "x.com" in u or "twitter.com" in u:
        return "x"
    return "unsupported_web"


def extract_username(url: str) -> str:
    """URL'nin son path segmentinden hedef kullanıcı adını çıkarır."""
    return (url or "").split("?")[0].rstrip("/").split("/")[-1].replace("@", "")


def ig_target_profile_update(ig_data: Any) -> dict:
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


async def scrape_instagram(
    url: str,
    cookie: str = "",
    log: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """Instagram profilini kazır ve target_profile güncellemesini döndürür.

    Kanıt yoksa (private/login duvarı/rate-limit) InsufficientEvidenceError
    yükseltir — asla boş veya sentetik profil ÜRETİLMEZ.
    `log(level, msg)` isteğe bağlı telemetri callback'idir (WS broadcast / CLI stderr).
    """
    emit = log or (lambda level, msg: None)
    username = extract_username(url)

    # [FAZ 5] STEALTH_PROVIDER seçici: default (env yok) = playwright_stealth
    # (bugünkü davranış); invisible/cloak yalnız binary operator tarafından
    # gösterildiyse available; kullanılamayan seçim dürüst loglanır ve tarama
    # stealthsiz devam eder (sahte gizlilik iddiası yok).
    from agent_core.services.stealth_provider import (
        apply_page_stealth,
        browser_kind,
        launch_overrides,
        resolve_stealth,
        use_invisible_module,
    )
    selection = resolve_stealth()
    emit("INFO", "STEALTH provider=%s available=%s%s" % (
        selection.provider, selection.available,
        (" reason=" + selection.reason) if selection.reason else "",
    ))

    if use_invisible_module(selection):
        from invisible_playwright.async_api import async_playwright as pw_factory
    else:
        from playwright.async_api import async_playwright as pw_factory

    async with pw_factory() as p:
        browser = None
        ctx = None
        page = None
        try:
            import os
            launch_kwargs = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
            if browser_kind(selection) == "chromium":
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                ]
                for cp in chrome_paths:
                    if os.path.exists(cp):
                        launch_kwargs["executable_path"] = cp
                        break
            launch_kwargs.update(launch_overrides(selection))

            launcher = p.firefox if browser_kind(selection) == "firefox" else p.chromium
            browser = await launcher.launch(**launch_kwargs)
            ctx_kwargs = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

            from agent_core.scraper.instagram_ghost import InstagramGhostScraper
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
            # [FAZ 5] Yalnız page-bazlı sağlayıcı (playwright_stealth) burada
            # uygulanır; launch-level (invisible/cloak) başlatım katmanındadır.
            # Uygulama başarısızsa dürüst loglanır ve tarama stealthsiz sürer.
            if selection.kind == "page" and selection.available:
                applied, note = await apply_page_stealth(selection, page)
                if not applied:
                    emit("WARNING", f"STEALTH apply başarısız: {note}")
            ig_scraper = InstagramGhostScraper(vault_cookies={"sessionid": cookie} if cookie else None)
            ig_data = await ig_scraper.scrape_async(username, playwright_page=page)

            # [024]/[025]/[026]: hizalı gerçek alanlar; sentetik post ÜRETİLMEZ.
            return ig_target_profile_update(ig_data)
        finally:
            for resource_name, resource in (("page", page), ("context", ctx), ("browser", browser)):
                if resource:
                    try:
                        await resource.close()
                    except Exception as cleanup_error:
                        emit("WARNING", f"SCRAPER CLEANUP: {resource_name} kapanamadı: {str(cleanup_error)[:80]}")


def build_user_context(
    rituals: List[str],
    playlist: List[str],
    envies: List[str],
) -> Dict[str, Any]:
    """Kullanıcı girdisinden payload'ın user_profile/user_context bölümlerini
    kurar ([009] sözleşmesi: boş girdi -> boş liste; örnek/placeholder ÜRETİLMEZ)."""
    return {
        "user_profile": {
            "private_rituals": rituals or [],
            "late_night_playlist": playlist or [],
            "secret_envies": envies or [],
        },
        "user_context": {
            "rituals": ", ".join(rituals or []),
            "playlist": ", ".join(playlist or []),
            "envies": ", ".join(envies or []),
        },
    }
