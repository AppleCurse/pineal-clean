"""GÖREV 1 — tamamlayici kazima sozlesmeleri.

Kapsam:
  1. /reel/ shortcode yakalama + post_type="reel" (is_video=True).
  2. video_url 1-to-1 dogrulanmis span ici eslesme (capraz-post sizma yasak).
  3. /p/ + /reel/ karisik belgede sira korunumu.
  4. Yapısal dugum: __typename/product_type -> post_type, video_url.
  5. Detay: JSON-LD @type + dugum turu/video birlesmesi.
  6. Kronolojik siralama t_0 -> t_N (stabil; tarihsizler sonda).
  7. Registry: post_types paralel listesi (posts_meta anahtar kumesi sabit).

Dogruluk ilkesi: bulunan alan alinir, bulunamayan ASLA uydurulmaz.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from agent_core.scraper.instagram_ghost import (
    InstagramGhostScraper,
    InstagramPost,
    InstagramProfile,
)
from agent_core.services.platform_registry import ig_target_profile_update


REEL_HTML = (
    '<html><head>'
    '<meta property="og:description" content="99 Followers, 10 Following, 5 Posts - r">'
    '</head><body><script>'
    '/p/PPP111/ lorem '
    '"display_url":"https://scontent.cdn.example/p1.jpg",'
    '/reel/RRR222/ lorem '
    '"display_url":"https://scontent.cdn.example/r2.jpg"'
    '</script></body></html>'
)

VIDEO_HTML = (
    '<html><head>'
    '<meta property="og:description" content="50 Followers"/>'
    '</head><body><script>'
    '"shortcode":"VVV1",'
    '"video_url":"https://scontent.cdn.example/v1.mp4",'
    '"display_url":"https://scontent.cdn.example/v1.jpg",'
    '"video_url":"https://scontent.cdn.example/orphan.mp4",'
    '"shortcode":"NNN2",'
    '"display_url":"https://scontent.cdn.example/n2.jpg"'
    '</script></body></html>'
)


# ------------------------------------------------------------------ #
# 1-3) /reel/ yakalama + video 1-to-1 + karisik sira
# ------------------------------------------------------------------ #
def test_reel_shortcode_captured_with_type():
    scraper = InstagramGhostScraper()
    profile = scraper._parse_real_profile({"_source": "meta_tags"}, REEL_HTML, "hedef")
    assert [p.shortcode for p in profile.posts] == ["PPP111", "RRR222"]
    assert profile.posts[0].post_type is None  # /p/ turun kaniti degil
    assert profile.posts[0].is_video is False
    assert profile.posts[1].post_type == "reel"
    assert profile.posts[1].is_video is True
    assert profile.posts[1].display_url == "https://scontent.cdn.example/r2.jpg"


def test_video_url_attaches_only_inside_verified_span():
    """Video, yalniz kendi (shortcode, gorsel) span'indaki posta baglanir."""
    scraper = InstagramGhostScraper()
    profile = scraper._parse_real_profile({"_source": "meta_tags"}, VIDEO_HTML, "hedef")
    assert [p.shortcode for p in profile.posts] == ["VVV1", "NNN2"]
    # VVV1: video span icinde -> baglanir.
    assert profile.posts[0].video_url == "https://scontent.cdn.example/v1.mp4"
    # NNN2: onceki span'in disindaki orphan video ona odunc VERILMEZ.
    assert profile.posts[1].video_url is None


def test_json_shortcodes_keep_priority_over_url_patterns():
    """JSON shortcode varsa /p/ ve /reel/ kalintilari golge etmez."""
    html = (
        '<html><head><meta property="og:description" content="5 Followers"/></head>'
        '<body><script>'
        '"shortcode":"JJJ1","display_url":"https://scontent.cdn.example/j1.jpg"'
        ' /p/SHADOW1/ /reel/SHADOW2/ '
        '</script></body></html>'
    )
    scraper = InstagramGhostScraper()
    profile = scraper._parse_real_profile({"_source": "meta_tags"}, html, "hedef")
    assert [p.shortcode for p in profile.posts] == ["JJJ1"]


# ------------------------------------------------------------------ #
# 4) Yapisal dugum tur/video haritasi
# ------------------------------------------------------------------ #
def test_structured_node_typename_and_video_mapping():
    raw = {
        "media": [
            {"shortcode": "AAA", "display_url": "https://x.example/a.jpg",
             "__typename": "GraphVideo",
             "video_url": "https://x.example/a.mp4",
             "taken_at_timestamp": 1714601400,
             "edge_liked_by": {"count": 10}, "edge_media_to_comment": {"count": 1}},
            {"shortcode": "BBB", "display_url": "https://x.example/b.jpg",
             "__typename": "GraphVideo", "product_type": "clips",
             "taken_at_timestamp": 1714601500},
            {"shortcode": "CCC", "display_url": "https://x.example/c.jpg",
             "__typename": "GraphSidecar", "taken_at_timestamp": 1714601600},
        ]
    }
    nodes = InstagramGhostScraper._collect_structured_posts(raw)
    by_code = {n["shortcode"]: n for n in nodes}
    assert by_code["AAA"]["post_type"] == "video"
    assert by_code["AAA"]["video_url"] == "https://x.example/a.mp4"
    assert by_code["AAA"]["taken_at"].year == 2024
    assert by_code["AAA"]["like_count"] == 10
    assert by_code["AAA"]["comment_count"] == 1
    # product_type clips GraphVideo'yu ezer: reel.
    assert by_code["BBB"]["post_type"] == "reel"
    assert by_code["CCC"]["post_type"] == "carousel"
    assert by_code["CCC"]["video_url"] is None


def test_structured_node_unknown_type_stays_none():
    raw = {"shortcode": "UUU", "display_url": "https://x.example/u.jpg"}
    nodes = InstagramGhostScraper._collect_structured_posts(raw)
    assert nodes[0]["post_type"] is None
    assert nodes[0]["video_url"] is None


# ------------------------------------------------------------------ #
# 5) Detay birlesmesi: tur + video
# ------------------------------------------------------------------ #
def test_detail_jsonld_videobject_sets_type_and_flag():
    html = (
        '<html><head>'
        '<meta property="og:url" content="https://www.instagram.com/reel/VID1/">'
        '<script type="application/ld+json">'
        '[{"@type":"VideoObject","uploadDate":"2024-06-01T10:00:00+00:00"}]'
        '</script></head><body>VID1 gonderi</body></html>'
    )
    detail = InstagramGhostScraper._extract_post_detail(html, "VID1")
    assert detail["post_type"] == "video"
    assert detail["is_video"] is True
    assert detail["taken_at"] == datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    assert "caption" not in detail  # yoksa uydurulmaz


def test_detail_embedded_node_type_and_video_merge():
    html = (
        '<html><head>'
        '<meta property="og:url" content="https://www.instagram.com/p/ND1/">'
        '</head><body><script>'
        'window._sharedData = {"x":{"shortcode":"ND1",'
        '"display_url":"https://scontent.cdn.example/n.jpg",'
        '"__typename":"GraphVideo",'
        '"video_url":"https://scontent.cdn.example/n.mp4",'
        '"taken_at_timestamp":1714601400}};'
        '</script></body></html>'
    )
    detail = InstagramGhostScraper._extract_post_detail(html, "ND1")
    assert detail["post_type"] == "video"
    assert detail["video_url"] == "https://scontent.cdn.example/n.mp4"
    assert detail["taken_at"].year == 2024


# ------------------------------------------------------------------ #
# 6) Kronolojik siralama
# ------------------------------------------------------------------ #
def _post(code, year=None, month=None, day=None):
    return InstagramPost(
        shortcode=code,
        display_url=f"https://scontent.cdn.example/{code}.jpg",
        taken_at=(datetime(year, month, day, tzinfo=timezone.utc)
                  if year else None),
    )


def test_sort_chronological_orders_dated_ascending():
    posts = [_post("C", 2024, 5, 3), _post("A", 2024, 5, 1), _post("B", 2024, 5, 2)]
    ordered = InstagramGhostScraper._sort_chronological(posts)
    assert [p.shortcode for p in ordered] == ["A", "B", "C"]


def test_sort_chronological_timeless_last_stable():
    posts = [_post("X"), _post("A", 2024, 5, 1), _post("Y")]
    ordered = InstagramGhostScraper._sort_chronological(posts)
    # Tarihli one gecer; tarihsizler sonda, gorece sirayla.
    assert [p.shortcode for p in ordered] == ["A", "X", "Y"]


async def test_scrape_async_sorts_after_enrichment_not_grid_order():
    """Grid sirasi ters olsa bile detay tarihleri kronolojiyi belirler."""

    class FakePage:
        def __init__(self):
            self.goto_urls = []
            self.current = ""

        async def goto(self, url, wait_until=None, timeout=None):
            self.goto_urls.append(url)
            self.current = url

        async def content(self):
            if self.current.rstrip("/").endswith("/NEW1"):
                return (
                    '<html><head>'
                    '<script type="application/ld+json">'
                    '{"@type":"ImageObject","uploadDate":"2024-05-03T00:00:00+00:00"}'
                    '</script></head><body>NEW1</body></html>'
                )
            if self.current.rstrip("/").endswith("/OLD2"):
                return (
                    '<html><head>'
                    '<script type="application/ld+json">'
                    '{"@type":"ImageObject","uploadDate":"2024-05-01T00:00:00+00:00"}'
                    '</script></head><body>OLD2</body></html>'
                )
            return (
                '<html><head>'
                '<meta property="og:description" content="9 Followers"/>'
                '</head><body><script>'
                '"shortcode":"NEW1","display_url":"https://scontent.cdn.example/n.jpg",'
                '"shortcode":"OLD2","display_url":"https://scontent.cdn.example/o.jpg"'
                '</script></body></html>'
            )

    scraper = InstagramGhostScraper()
    page = FakePage()
    with patch.object(scraper, "_random_delay", new_callable=AsyncMock), \
         patch.object(scraper, "_post_detail_delay", new_callable=AsyncMock):
        profile = await scraper.scrape_async("hedef", playwright_page=page)
    # Grid: NEW1 once; kronoloji: OLD2 (05-01) once.
    assert [p.shortcode for p in profile.posts] == ["OLD2", "NEW1"]
    # goto sirasi belge sirasinda kalir (sira kilidi).
    assert page.goto_urls[1].endswith("/p/NEW1/")
    assert page.goto_urls[2].endswith("/p/OLD2/")


# ------------------------------------------------------------------ #
# 7) Registry post_types hizalamasi
# ------------------------------------------------------------------ #
def test_registry_post_types_aligned_and_meta_keys_frozen():
    profile = InstagramProfile(
        username="h", is_private=False,
        posts=[
            InstagramPost(shortcode="A", display_url="https://x.example/a.jpg",
                          post_type="image"),
            InstagramPost(shortcode="B", display_url="https://x.example/b.jpg",
                          post_type="reel"),
            InstagramPost(shortcode="C", display_url="https://x.example/c.jpg"),
        ],
    )
    update = ig_target_profile_update(profile)
    assert update["post_types"] == ["image", "reel", "unknown"]
    assert len(update["posts"]) == len(update["post_times"]) == \
        len(update["posts_meta"]) == len(update["post_types"]) == 3
    assert set(update["posts_meta"][0].keys()) == {"like_count", "comment_count"}


def test_post_model_new_fields_default_none():
    p = InstagramPost(shortcode="A", display_url="https://x.example/a.jpg")
    assert p.post_type is None
    assert p.video_url is None
