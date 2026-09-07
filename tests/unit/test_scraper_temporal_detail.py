"""FAZ 1 — kaziyici zaman boyutu sozlesmeleri.

Kapsam:
  1. Konum bazli shortcode<->display_url eslesmesi (index-zip hizalama hatasi bitti).
  2. Tekil post sayfasindan caption/taken_at/like/comment cikarma (saf fonksiyon).
  3. scrape_async zenginlestirme adimi: eksik alan dolar, grid degeri ezilmez,
     hata/duvar profili oldurmez, env ile kapatilabilir/limitlenebilir.
  4. temporal_coverage + confidence bonus-only (mevcut 0.6 esik sozlesmesi korunur).

Dogruluk ilkesi: bulunan alan alinir, bulunamayan ASLA uydurulmaz.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from agent_core.scraper.instagram_ghost import (
    InstagramGhostScraper,
    InstagramPost,
    InstagramProfile,
)


PROFILE_HTML = (
    '<html><head>'
    '<meta property="og:description" content="1,204 Followers, 310 Following, 42 Posts - n">'
    '<meta property="og:title" content="Hedef (@hedef) - Instagram photos and videos">'
    '<meta property="og:image" content="https://scontent.cdn.example/pp.jpg">'
    '</head><body><script>'
    '"shortcode":"AAA111","display_url":"https://scontent.cdn.example/a1.jpg",'
    '"edge_media_to_caption":{"edges":[{"node":{"text":"grid caption bir"}}]},'
    '"shortcode":"BBB222","display_url":"https://scontent.cdn.example/a2.jpg"'
    '</script></body></html>'
)

# AAA111: gomulu JSON (1. oncelik) + JSON-LD + meta; JSON kazanmali.
POST_HTML_AAA = (
    '<html><head>'
    '<meta property="og:url" content="https://www.instagram.com/p/AAA111/">'
    '<meta property="article:published_time" content="2024-05-01T23:30:00+00:00">'
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"ImageObject",'
    '"uploadDate":"2024-05-01T23:30:00Z","caption":"detay caption bir"}'
    '</script></head><body><script>'
    'window._sharedData = {"x":{"shortcode":"AAA111",'
    '"display_url":"https://scontent.cdn.example/a1.jpg",'
    '"taken_at_timestamp":1714601400,"is_video":false,'
    '"edge_media_to_caption":{"edges":[{"node":{"text":"json caption bir"}}]},'
    '"edge_liked_by":{"count":45},"edge_media_to_comment":{"count":3}}};'
    '</script></body></html>'
)

# BBB222: yalniz JSON-LD tarihi; caption/count yok -> None kalmali.
POST_HTML_BBB = (
    '<html><head>'
    '<meta property="og:url" content="https://www.instagram.com/p/BBB222/">'
    '<script type="application/ld+json">'
    '[{"@type":"VideoObject","uploadDate":"2024-05-03T04:10:00+00:00"}]'
    '</script></head><body>BBB222 gonderi icerigi</body></html>'
)

POST_HTML_LOGIN = (
    '<html><body>Login \u2022 Instagram '
    'name="username" name="password" AAA111</body></html>'
)


class FakePage:
    """URL'ye gore konserve HTML donduren sahte Playwright sayfasi."""

    def __init__(self, profile_html, post_pages):
        self.profile_html = profile_html
        self.post_pages = post_pages
        self.current = ""
        self.goto_urls = []

    async def goto(self, url, wait_until=None, timeout=None):
        self.goto_urls.append(url)
        self.current = url

    async def content(self):
        if "/p/" in self.current:
            shortcode = self.current.rstrip("/").rsplit("/", 1)[-1]
            if shortcode in self.post_pages:
                return self.post_pages[shortcode]
            raise Exception("net::ERR_CONNECTION_TIMED_OUT timeout")
        return self.profile_html


def _no_delays(scraper):
    return (
        patch.object(scraper, "_random_delay", new_callable=AsyncMock),
        patch.object(scraper, "_post_detail_delay", new_callable=AsyncMock),
    )


# ------------------------------------------------------------------ #
# 1) Konum bazli eslesme
# ------------------------------------------------------------------ #
def test_pairing_matches_shortcode_to_following_image_in_order():
    scraper = InstagramGhostScraper()
    profile = scraper._parse_real_profile({"_source": "meta_tags"}, PROFILE_HTML, "hedef")
    assert [p.shortcode for p in profile.posts] == ["AAA111", "BBB222"]
    assert profile.posts[0].display_url == "https://scontent.cdn.example/a1.jpg"
    assert profile.posts[1].display_url == "https://scontent.cdn.example/a2.jpg"
    assert profile.posts[0].caption == "grid caption bir"
    assert profile.posts[1].caption is None


def test_pairing_does_not_steal_shortcode_across_posts():
    """Gorsel, kendinden SONRA gelen shortcode'u calmamali (index-zip hatasi)."""
    html = (
        '<html><head><meta property="og:description" content="5 Followers"/></head>'
        '<body><script>'
        '"display_url":"https://scontent.cdn.example/early.jpg",'
        '"shortcode":"LATE1","display_url":"https://scontent.cdn.example/late.jpg"'
        '</script></body></html>'
    )
    scraper = InstagramGhostScraper()
    profile = scraper._parse_real_profile({"_source": "meta_tags"}, html, "hedef")
    assert len(profile.posts) == 2
    # Belge sirasi korunur: once eslesmeyen kurtarma, sonra eslesen.
    assert profile.posts[0].shortcode == "post_1"
    assert profile.posts[0].display_url == "https://scontent.cdn.example/early.jpg"
    assert profile.posts[1].shortcode == "LATE1"
    assert profile.posts[1].display_url == "https://scontent.cdn.example/late.jpg"


def test_pairing_lone_display_url_still_recovered():
    html = (
        '<html><head><meta property="og:description" content="5 Followers"/></head>'
        '<body><script>"display_url":"https://scontent.cdn.example/solo.jpg"</script>'
        '</body></html>'
    )
    scraper = InstagramGhostScraper()
    profile = scraper._parse_real_profile({"_source": "meta_tags"}, html, "hedef")
    assert len(profile.posts) == 1
    assert profile.posts[0].display_url == "https://scontent.cdn.example/solo.jpg"
    assert profile.posts[0].taken_at is None


# ------------------------------------------------------------------ #
# 2) Post-detay cikarma (saf fonksiyon)
# ------------------------------------------------------------------ #
def test_detail_prefers_embedded_json_over_jsonld():
    detail = InstagramGhostScraper._extract_post_detail(POST_HTML_AAA, "AAA111")
    assert detail["caption"] == "json caption bir"
    assert detail["taken_at"].year == 2024
    assert detail["taken_at"].month == 5
    assert detail["taken_at"].day == 1
    assert detail["like_count"] == 45
    assert detail["comment_count"] == 3


def test_detail_jsonld_date_without_caption_stays_honest():
    detail = InstagramGhostScraper._extract_post_detail(POST_HTML_BBB, "BBB222")
    assert detail["taken_at"] == datetime(2024, 5, 3, 4, 10, tzinfo=timezone.utc)
    assert "caption" not in detail
    assert "like_count" not in detail
    assert "comment_count" not in detail


def test_detail_login_wall_returns_empty():
    assert InstagramGhostScraper._extract_post_detail(POST_HTML_LOGIN, "AAA111") == {}


def test_detail_shortcode_mismatch_returns_empty():
    # Shortcode sayfada yoksa yanlis sayfa -> bilesim yasak.
    assert InstagramGhostScraper._extract_post_detail(POST_HTML_BBB, "ZZZ999") == {}


def test_detail_placeholder_shortcode_rejected():
    assert InstagramGhostScraper._extract_post_detail(POST_HTML_AAA, "post_1") == {}
    assert InstagramGhostScraper._extract_post_detail("", "AAA111") == {}


# ------------------------------------------------------------------ #
# 3) scrape_async zenginlestirme adimi
# ------------------------------------------------------------------ #
async def test_scrape_async_enriches_missing_fields_without_overwriting_grid():
    scraper = InstagramGhostScraper()
    page = FakePage(PROFILE_HTML, {"AAA111": POST_HTML_AAA, "BBB222": POST_HTML_BBB})
    delay_patches = _no_delays(scraper)
    with delay_patches[0], delay_patches[1]:
        profile = await scraper.scrape_async("hedef", playwright_page=page)

    # Sira korunur (belge sirasi).
    assert [p.shortcode for p in profile.posts] == ["AAA111", "BBB222"]
    # AAA111: grid caption EZILMEZ, eksik tarih/sayilar detaydan dolar.
    assert profile.posts[0].caption == "grid caption bir"
    assert profile.posts[0].taken_at is not None
    assert profile.posts[0].taken_at.year == 2024
    assert profile.posts[0].like_count == 45
    assert profile.posts[0].comment_count == 3
    # BBB222: JSON-LD tarihi dolar, olmayan caption/count None kalir.
    assert profile.posts[1].taken_at == datetime(2024, 5, 3, 4, 10, tzinfo=timezone.utc)
    assert profile.posts[1].caption is None
    assert profile.posts[1].like_count is None
    # 1 profil + 2 post istegi.
    assert len(page.goto_urls) == 3
    assert page.goto_urls[0].endswith("/hedef/")
    assert page.goto_urls[1].endswith("/p/AAA111/")
    assert page.goto_urls[2].endswith("/p/BBB222/")


async def test_scrape_async_detail_failure_keeps_grid_data():
    """Post sayfasi hata verirse profil grid verisiyle yasar (olum yok)."""
    scraper = InstagramGhostScraper()
    page = FakePage(PROFILE_HTML, {})  # tum post nav'leri timeout
    delay_patches = _no_delays(scraper)
    with delay_patches[0], delay_patches[1]:
        profile = await scraper.scrape_async("hedef", playwright_page=page)

    assert [p.shortcode for p in profile.posts] == ["AAA111", "BBB222"]
    assert profile.posts[0].caption == "grid caption bir"
    assert profile.posts[0].taken_at is None


async def test_scrape_async_detail_disabled_via_env(monkeypatch):
    monkeypatch.setenv("PINEAL_POST_DETAIL_ENABLED", "false")
    scraper = InstagramGhostScraper()
    page = FakePage(PROFILE_HTML, {"AAA111": POST_HTML_AAA, "BBB222": POST_HTML_BBB})
    delay_patches = _no_delays(scraper)
    with delay_patches[0], delay_patches[1]:
        profile = await scraper.scrape_async("hedef", playwright_page=page)

    assert page.goto_urls == [f"{scraper.base_url}/hedef/"]
    assert all(p.taken_at is None for p in profile.posts)


async def test_scrape_async_detail_limit_caps_requests(monkeypatch):
    monkeypatch.setenv("PINEAL_POST_DETAIL_LIMIT", "1")
    scraper = InstagramGhostScraper()
    page = FakePage(PROFILE_HTML, {"AAA111": POST_HTML_AAA, "BBB222": POST_HTML_BBB})
    delay_patches = _no_delays(scraper)
    with delay_patches[0], delay_patches[1]:
        profile = await scraper.scrape_async("hedef", playwright_page=page)

    assert len(page.goto_urls) == 2  # profil + 1 post
    assert profile.posts[0].taken_at is not None
    assert profile.posts[1].taken_at is None


# ------------------------------------------------------------------ #
# 4) temporal_coverage + bonus-only confidence
# ------------------------------------------------------------------ #
def _strong_profile(dated: int) -> InstagramProfile:
    posts = []
    for i in range(3):
        posts.append(InstagramPost(
            shortcode=f"C{i}",
            display_url=f"https://scontent.cdn.example/{i}.jpg",
            taken_at=datetime(2024, 5, 1 + i, tzinfo=timezone.utc) if i < dated else None,
        ))
    return InstagramProfile(
        username="guclu", biography="Gercek bir bio", is_private=False,
        follower_count=1000, posts=posts,
    )


def test_temporal_coverage_counts_dated_posts():
    assert InstagramGhostScraper.temporal_coverage(_strong_profile(0)) == 0.0
    assert InstagramGhostScraper.temporal_coverage(_strong_profile(2)) == 0.667
    empty = InstagramProfile(username="bos", is_private=False, posts=[])
    assert InstagramGhostScraper.temporal_coverage(empty) == 0.0


def test_confidence_bonus_only_preserves_legacy_thresholds():
    """Mevcut sozlesmeler: tarihsiz guclu >= 0.6, zayif < 0.6, private <= 0.4."""
    scraper = InstagramGhostScraper()
    undated = scraper.evaluate_confidence(_strong_profile(0))
    dated = scraper.evaluate_confidence(_strong_profile(2))
    assert undated >= 0.6
    assert dated > undated  # tarihli profil odullendirilir

    weak = InstagramProfile(username="zayif", is_private=False, posts=[])
    assert scraper.evaluate_confidence(weak) < 0.6

    private = _strong_profile(3)
    private.is_private = True
    assert scraper.evaluate_confidence(private) <= 0.4
