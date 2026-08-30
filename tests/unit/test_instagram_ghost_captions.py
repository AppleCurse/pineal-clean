"""[196 canli-kosu duzeltmesi] Regresyon kilidi.

1. instagram_ghost regex-kurtarma yolu (yapısal JSON bulunamadığında düşen
   yol) eskiden her postu caption=None ile yazıyordu; oysa kırpılan HTML'de
   altyazı JSON'u çoğu zaman duruyor. Düzeltme sonrası shortcode-penceresinden
   altyazı kurtarılır; bulunamazsa DÜRÜSTÇE None kalır (uydurma yok).
2. baslat.bat tek-komut kurulumda requirements-osint.txt'yi VE Playwright
   chromium'u kurmak zorunda (canlı koşuda ikisi de eksikti -> OSINT ayak
   izi %0 + cognitive_profiler verisiz + kazıma riskli).
"""

from pathlib import Path

from agent_core.scraper.instagram_ghost import InstagramGhostScraper

REPO_ROOT = Path(__file__).resolve().parents[2]
BASLAT = REPO_ROOT / "baslat.bat"

HTML_BASE = (
    '<html><head><meta property="og:description" content="bio"/></head><body>'
)


def _parse(html: str):
    scraper = InstagramGhostScraper()
    return scraper._parse_real_profile({"_source": "meta_tags"}, html, "testuser")


def test_fallback_recovers_caption_from_shortcode_window():
    """Yapısal JSON yokken bile altyazı kurtarılmalı (caption=None çöp kuralı)."""
    html = (
        HTML_BASE
        + '"shortcode":"DefGhi_1","display_url":"https://scontent/1.jpg\\u0026se=7",'
        + '"edge_media_to_caption":{"edges":[{"node":{"text":"kizim ve meyhane geceleri \\u2665"}}]}'
        + "</body></html>"
    )
    profile = _parse(html)
    assert len(profile.posts) == 1
    post = profile.posts[0]
    assert post.shortcode == "DefGhi_1"
    assert post.caption is not None, "regex yolu altyazıyı yine çöpe attı"
    assert "meyhane" in post.caption
    # gömülü JSON kaçışları çözülmeli
    assert post.display_url == "https://scontent/1.jpg&se=7"


def test_fallback_without_caption_keeps_none():
    """HTML'de altyazı yoksa caption None kalmalı — uydurma yasak."""
    html = (
        HTML_BASE
        + '"shortcode":"AbC123","display_url":"https://scontent/2.jpg"'
        + "</body></html>"
    )
    profile = _parse(html)
    assert len(profile.posts) == 1
    assert profile.posts[0].caption is None


def test_baslat_installs_osint_stack_and_browser():
    """Tek-komut launcher: OSINT yığını + tarayıcı motoru kurulum zorunluluğu."""
    assert BASLAT.exists(), "baslat.bat kayıp"
    text = BASLAT.read_text(encoding="utf-8")
    req_pos = text.find("requirements.txt")
    osint_pos = text.find("requirements-osint.txt")
    browser_pos = text.find("playwright install chromium")
    assert req_pos != -1, "requirements.txt kurulum satırı kayıp"
    assert osint_pos != -1, "OSINT yığını launcher'dan hiç kurulmuyor"
    assert browser_pos != -1, "Playwright chromium launcher'dan kurulmuyor"
    assert req_pos < osint_pos, "kurulum sırası: önce temel, sonra OSINT (psutil iki-adım kuralı)"
    # OSINT kurulumu patlarsa launch tamamen ölmemeli (psutil geçmişi) — uyarı + devam
    fail_count = text.count("goto :fail")
    osint_block = text[text.find("requirements-osint.txt") : text.find("REM --- 3")]
    assert "goto :fail" not in osint_block, "OSINT kurulum hatası tüm başlatmayı öldürmemeli"


def test_baslat_pins_working_dir_and_guards_port():
    """Gerçek-koşu arızası: ikinci başlatışta 8000 portu çakışması + çift tıklamada
    yanlış çalışma klasörü. Port koruması ve klasör sabitleme zorunlu."""
    assert BASLAT.exists()
    text = BASLAT.read_text(encoding="utf-8")
    assert 'cd /d "%~dp0"' in text, "çalışma klasörü .bat'ın konumuna sabitlenmeli"
    assert "curl.exe" in text and "netstat" in text, "8000 port koruması olmalı"
    assert "Zaten calisiyor" in text or "zaten calisiyor" in text, "sunucu açıksa ikinci kopya başlatmamalı"
