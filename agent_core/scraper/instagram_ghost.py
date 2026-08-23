"""
PINEAL-HERETIC v2.0 - Instagram Ghost Scraper (Self-Hosted)
Faz 5 / Görev 3 - Türkiye Operasyonu

Mimari Karar: Sıfır SaaS, sıfır Apify, sıfır kart.
X scraper.py'nin ikizi - Playwright hayalet tarayıcı, kendi bilgisayarında çalışır.
Halüsinasyon = 0. Kanıt yoksa HALT.

Bu modül asla veri uydurmaz. Instagram'ın döndüğü gerçek JSON'u alır,
Pydantic V2 ile doğrular, güven düşükse InsufficientEvidenceError fırlatır.
"""

from __future__ import annotations
import json
import random
import re
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
import html as html_lib

from pydantic import BaseModel, Field, ConfigDict, field_validator


# --- Anti-Halüsinasyon Çekirdeği ---
class InsufficientEvidenceError(Exception):
    """Kanıt yoksa uydurma, DUR. Faz 4 kuralı."""


# --- Pydantic V2 Şemalar (ConfigDict, extra="forbid" - halüsinasyon filtresi) ---
class InstagramPost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    shortcode: str = Field(..., description="Post ID, örn: C123...")
    caption: Optional[str] = Field(None, max_length=2200)
    display_url: str = Field(..., description="Fotoğrafın gerçek URL'i, uydurma değil")
    is_video: bool = False
    location_name: Optional[str] = None
    taken_at: Optional[datetime] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None

    @field_validator("display_url")
    @classmethod
    def url_must_be_real(cls, v: str) -> str:
        if not v.startswith("http"):
            raise ValueError("Sahte URL halüsinasyondur")
        return v


class InstagramProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    is_private: bool
    is_verified: bool = False
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    profile_pic_url: Optional[str] = None
    posts: List[InstagramPost] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_source: str = Field(default="self_hosted_ghost_browser", description="Kanıtın nereden geldiği, şeffaflık için")

    @field_validator("posts")
    @classmethod
    def posts_must_be_real(cls, v: List[InstagramPost]) -> List[InstagramPost]:
        # 12 posttan fazla istemiyoruz, OSINT için yeterli
        return v[:12]


class InstagramGhostScraper:
    """
    Self-hosted hayalet kazıyıcı.
    X scraper.py ile aynı mimari: Playwright, vault'tan cookie, stealth.
    Asla veri uydurmaz.
    """

    def __init__(self, vault_cookies: Optional[Dict[str, str]] = None):
        self.vault_cookies = vault_cookies or {}
        self.base_url = "https://www.instagram.com"

    def _random_delay(self):
        """İnsan gibi bekle, bot gibi değil."""
        time.sleep(random.uniform(2.0, 5.0))

    def _extract_from_html(self, html: str, username: str) -> Dict[str, Any]:
        """
        Instagram'ın sayfa içine gömdüğü JSON'u veya public meta tag'lerini bul.
        """
        patterns = [
            r'window\._sharedData\s*=\s*({.*?});</script>',
            r'"ProfilePage":\s*\[({.*?})\]',
            r'"userData":\s*({.*?}),"',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return data
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to parse JSON in instagram_ghost: {e}")
                    continue
        
        # Meta tag fallback (Modern Instagram web sayfaları)
        if "og:description" in html or "og:title" in html:
            return {"_source": "meta_tags"}

        raise InsufficientEvidenceError(f"Instagram HTML'inde JSON bulunamadı: {username} - muhtemelen private veya rate-limit")


    @staticmethod
    def _parse_num(val_str: Optional[str]) -> Optional[int]:
        if not val_str:
            return None
        clean = val_str.strip().upper().replace(',', '').replace(' ', '')
        try:
            if clean.endswith('M'):
                return int(float(clean[:-1]) * 1_000_000)
            elif clean.endswith('K'):
                return int(float(clean[:-1]) * 1_000)
            else:
                return int(float(clean))
        except Exception:
            return None

    def _extract_counts(self, html: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        follower_count = None
        following_count = None
        post_count = None
        og_desc_match = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        if og_desc_match:
            og_desc = og_desc_match.group(1)
            fol_m = re.search(r'([\d\.,]+(?:\s*[KMkm])?)\s*(?:Takipçi|Followers)', og_desc, re.IGNORECASE)
            if fol_m:
                follower_count = self._parse_num(fol_m.group(1))
            fing_m = re.search(r'([\d\.,]+(?:\s*[KMkm])?)\s*(?:Takip\b|Following)', og_desc, re.IGNORECASE)
            if fing_m:
                following_count = self._parse_num(fing_m.group(1))
            post_m = re.search(r'([\d\.,]+(?:\s*[KMkm])?)\s*(?:Gönderi|Posts)', og_desc, re.IGNORECASE)
            if post_m:
                post_count = self._parse_num(post_m.group(1))
        return follower_count, following_count, post_count

    def _extract_full_name(self, html: str) -> Optional[str]:
        og_title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if og_title_match:
            name_m = re.search(r'^(.*?)\s*(?:\(@|•|\-)', og_title_match.group(1))
            if name_m:
                return name_m.group(1).strip()
        return None

    def _extract_biography(self, html: str) -> Optional[str]:
        bio_match = re.search(r'<meta\s+content="[^"]*(?:Instagram\'da|on Instagram):\s*&quot;([^&]*)&quot;"', html)
        if bio_match:
            return html_lib.unescape(bio_match.group(1).strip())

        og_desc_match = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        if og_desc_match and " - " in og_desc_match.group(1):
            parts = og_desc_match.group(1).split(" - ", 1)
            if len(parts) > 1 and not parts[1].startswith("See Instagram") and not parts[1].startswith("Instagram fotoğraflarını"):
                return parts[1].strip()
        return None

    def _extract_profile_pic(self, html: str) -> Optional[str]:
        profile_pic_match = re.search(r'<meta property="og:image" content="([^"]+)"', html) or re.search(r'"profile_pic_url":"([^"]+)"', html)
        return profile_pic_match.group(1).replace("&amp;", "&").replace("\\u0026", "&") if profile_pic_match else None

    def _extract_posts(self, html: str) -> List[InstagramPost]:
        posts = []
        shortcodes = re.findall(r'"shortcode":"([A-Za-z0-9_-]+)"', html) or re.findall(r'/p/([A-Za-z0-9_-]+)/', html)
        display_urls = re.findall(r'"display_url":"([^"]+)"', html)

        if not display_urls:
            for m in re.finditer(r'https://scontent[^\s"\'<>&]+\.jpg[^\s"\'<>]*', html):
                url = m.group(0).replace("&amp;", "&").replace("\\u0026", "&")
                if url not in display_urls and ("s150x150" not in url and "s320x320" not in url):
                    display_urls.append(url)

        for i in range(min(len(display_urls), 12)):
            try:
                sc = shortcodes[i] if i < len(shortcodes) else f"post_{i+1}"
                url = display_urls[i].replace("\\u0026", "&")
                posts.append(InstagramPost(
                    shortcode=sc,
                    display_url=url,
                    caption=None,
                    is_video=False
                ))
            except Exception:
                continue
        return posts


    def _parse_real_profile(self, raw_json: Dict[str, Any], html: str, username: str) -> InstagramProfile:
        """
        Ham JSON veya meta tag'leri gerçek Pydantic modele çevirir.
        """
        try:
            is_private = '"is_private":true' in html or '"isPrivate":true' in html or 'Bu hesap gizli' in html or 'This account is private' in html

            follower_count, following_count, post_count = self._extract_counts(html)
            full_name = self._extract_full_name(html)
            biography = self._extract_biography(html)
            profile_pic_url = self._extract_profile_pic(html)
            posts = self._extract_posts(html)

            # Eğer private ve post yoksa, sonraki ajanlar boş veriyle halüsinasyon göreceği için durdur

            if is_private and len(posts) == 0:
                raise InsufficientEvidenceError(f"Hedef profil gizli (Private) ve gönderi okunamıyor: {username}")

            profile = InstagramProfile(
                username=username,
                full_name=full_name,
                biography=biography,
                is_private=is_private,
                follower_count=follower_count,
                following_count=following_count,
                post_count=post_count,
                profile_pic_url=profile_pic_url,
                posts=posts,
                evidence_source="self_hosted_ghost_browser"
            )

            # --- ANTI-HALÜSİNASYON KONTROLÜ ---
            # Eğer hem follower yok, hem bio yok, hem post yok -> bu sayfa boş, HALT
            if follower_count is None and biography is None and len(posts) == 0 and not is_private:
                raise InsufficientEvidenceError(f"Instagram profili boş geldi: {username} - rate-limit veya sayfa yapısı değişmiş")

            return profile

        except InsufficientEvidenceError:
            raise
        except Exception as e:
            # Beklenmedik parse hatası -> halüsinasyon yapma, halt et
            raise InsufficientEvidenceError(f"Instagram parse hatası, veri uydurmuyorum: {username} - {str(e)}")

    async def scrape_async(self, username: str, playwright_page=None) -> InstagramProfile:
        """
        Ana metod - Playwright page dışarıdan verilir (X scraper ile aynı vault izolasyonu)
        Eğer page yoksa, senkron fallback için hata fırlatır - uydurma tarayıcı açmaz.
        """
        if playwright_page is None:
            raise InsufficientEvidenceError("Playwright page verilmedi - hayalet tarayıcı vault'tan gelmeli, kendi kendine açmam")

        target_url = f"{self.base_url}/{username}/"
        
        import asyncio
        import logging
        
        html = ""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Stealth navigation
                await playwright_page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                self._random_delay()
                html = await playwright_page.content()
                break
            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(term in err_str for term in ["timeout", "net::", "reset", "disconnected", "closed", "failed"])
                if not is_transient:
                    logging.error(f"Playwright permanent error on attempt {attempt+1}: {e}")
                    raise InsufficientEvidenceError(f"Scraper kalıcı hatası: {username} - {str(e)}") from e
                
                logging.warning(f"Playwright transient failure (attempt {attempt+1}/{max_retries}), Reason: {e}")
                if attempt == max_retries - 1:
                    logging.error(f"Playwright final failure after {max_retries} attempts.")
                    raise InsufficientEvidenceError(f"Scraper network timeout/transient hatası: {username} - {str(e)}") from e
                await asyncio.sleep(2)

        # Login duvarı mı?
        if "Login • Instagram" in html or 'name="username"' in html and 'name="password"' in html:
            raise InsufficientEvidenceError(f"Instagram login duvarı: {username} - cookie expired, vault'u yenile")

        # Rate limit duvarı mı?
        if "Try again later" in html or "We restrict certain activity" in html:
            raise InsufficientEvidenceError(f"Instagram rate-limit: {username} - bekle ve tekrar dene")

        raw = self._extract_from_html(html, username)
        profile = self._parse_real_profile(raw, html, username)

        return profile

    def evaluate_confidence(self, profile: InstagramProfile) -> float:
        """
        Uncertainty Engine için güven skoru.
        Düşükse HALT.
        """
        score = 0.0
        if profile.follower_count is not None:
            score += 0.2
        if profile.biography:
            score += 0.2
        if len(profile.posts) >= 3:
            score += 0.4
        elif len(profile.posts) >= 1:
            score += 0.2
        
        if profile.is_private:
            score = min(score, 0.4)  # Private ise max 0.4 - yetersiz kanıt

        # Eğer skor < 0.6 ise, task_executor bunu halt etmeli
        return round(score, 2)
