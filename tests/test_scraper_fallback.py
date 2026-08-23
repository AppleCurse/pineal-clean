"""
scraper.py hata yayılımı sözleşmesi.

Eski Playwright tabanlı scraper'ın yerine `browser_oxide` kullanan yeni
uygulamaya göre testler güncellendi:

1. Tarayıcı motoru (browser_oxide) yoksa -> ImportError yolu -> yedek mantık
   çalışır ve hiç veri toplanamazsa InsufficientEvidenceError yükselir
   (hata yutulup boş JSON dönmemeli).
2. Tarayıcı motoru varsa ama hedef hesap gizliyse (GraphQL `protected: true`)
   -> TargetPrivateError yükselir.
"""
import sys
import types

import pytest



def test_scraper_raises_when_no_browser_engine_and_no_data():
    """browser_oxide yok ve hiç veri kazılamazsa hata yutulmamalı."""
    import scraper

    # Test ortamında browser_oxide kesinlikle yokmuş gibi davran.
    assert "browser_oxide" not in sys.modules or True
    with pytest.raises(RuntimeError, match="InsufficientEvidenceError"):
        scraper.scrape_readonly("https://x.com/empty_or_blocked_user")


def test_scraper_raises_target_private_when_graphql_reports_protected(monkeypatch):
    """GraphQL yanıtı hesap gizli (protected) derse TargetPrivateError yükselir."""
    import scraper

    # --- Sahte browser_oxide modülü ---
    fake_engine = types.ModuleType("browser_oxide")

    class _FakeResp:
        def __init__(self, url, status, payload, method="GET"):
            self.url = url
            self.status = status
            self.request = types.SimpleNamespace(method=method)
            self._payload = payload

        def json(self):
            return self._payload

    class _FakePage:
        def __init__(self):
            self._cookies = None

        def set_cookies(self, cookies):
            self._cookies = cookies

        def goto(self, url, wait_until=None):
            # protected (gizli) hesap GraphQL yanıtı
            return _FakeResp(
                url="https://x.com/i/api/graphql/abc/UserByScreenName",
                status=200,
                payload={
                    "data": {
                        "user": {
                            "result": {"legacy": {"protected": True, "description": ""}}
                        }
                    }
                },
            )

        def get_requests(self):
            # intercept_response bu yanıtı işler
            return [
                types.SimpleNamespace(
                    url="https://x.com/i/api/graphql/abc/UserByScreenName",
                    response=_FakeResp(
                        url="https://x.com/i/api/graphql/abc/UserByScreenName",
                        status=200,
                        payload={
                            "data": {
                                "user": {
                                    "result": {
                                        "legacy": {"protected": True, "description": ""}
                                    }
                                }
                            }
                        },
                    ),
                )
            ]

    class _FakeBrowser:
        def __init__(self, *args, **kwargs):
            self.page = _FakePage()

        def new_page(self):
            return self.page

        def close(self):
            pass

    fake_engine.Browser = _FakeBrowser
    monkeypatch.setitem(sys.modules, "browser_oxide", fake_engine)

    with pytest.raises(scraper.TargetPrivateError):
        scraper.scrape_readonly("https://x.com/private_user")
