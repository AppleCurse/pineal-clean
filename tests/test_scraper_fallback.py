"""
scraper.py (X kazima) B4 sözleşmesi.

B4 kararı: browser_oxide kaldırıldı; X kazima yolu açıkça
"desteklenmiyor" durumuna getirildi. Sözleşme:
  1) scrape_readonly her çağrıda XScraperUnsupportedError fırlatır
     (uydurma veri yok, sessiz boş JSON yok).
  2) main() --stdin akışı failed JSON + exit 1 döner.
  3) Kaynak kodu browser_oxide referansı içermez.
"""

import inspect
import json
import sys
import types

import pytest

import scraper


def test_scrape_readonly_raises_unsupported():
    with pytest.raises(scraper.XScraperUnsupportedError, match="desteklenmiyor"):
        scraper.scrape_readonly("https://x.com/some_user")


def test_scrape_readonly_raises_even_with_cookies():
    with pytest.raises(scraper.XScraperUnsupportedError):
        scraper.scrape_readonly("https://x.com/some_user", cookies="auth_token=abc")


def test_main_stdin_returns_failed_json(monkeypatch, capsys):
    payload = json.dumps({"target_url": "https://x.com/some_user"})
    monkeypatch.setattr(sys, "argv", ["scraper.py", "--stdin"])
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(read=lambda: payload))
    with pytest.raises(SystemExit) as exc:
        scraper.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    data = json.loads(out.strip().splitlines()[-1])
    assert data["status"] == "failed"
    assert "desteklenmiyor" in data["error"]


def test_source_has_no_browser_oxide_reference():
    """Kaynakta browser_oxide'a KOD referansi olmamali (docstring aciklamasi serbest)."""
    import ast
    tree = ast.parse(inspect.getsource(scraper))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name == "browser_oxide" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "browser_oxide"
        if isinstance(node, ast.Attribute):
            assert not (isinstance(node.value, ast.Name) and node.value.id == "browser_oxide")
