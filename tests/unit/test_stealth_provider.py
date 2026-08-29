"""Stealth sağlayıcı seçici sözleşme testleri (FAZ 5).

İlkeler:
- STEALTH_PROVIDER unset => playwright_stealth (MEVCUT davranış birebir).
- Geçersiz değer => sessiz değişim yok: default'a döner + makine-okunur sebep.
- invisible/cloak binary İNDİRMEZ: yalnız operator binary gösterdüyse available.
- invisible launch-level'dır; page-bazlı apply dürüstçe reddedilir.
- Registry: kullanılamayan seçimde tarama stealthsiz sürer ve sebep loglanır.
"""
import sys
import types

import pytest
from fastapi.testclient import TestClient

from agent_core.services.platform_registry import scrape_instagram
from agent_core.services.stealth_provider import (
    browser_kind,
    launch_overrides,
    resolve_stealth,
    use_invisible_module,
    CLOAK_BINARY_ENV,
    INVISIBLE_BINARY_ENV,
)


def _env(**kw):
    base = {"PATH": "/usr/bin"}
    base.update(kw)
    return base


class TestResolve:
    def test_default_is_playwright_stealth(self, monkeypatch):
        monkeypatch.delenv("STEALTH_PROVIDER", raising=False)
        sel = resolve_stealth(env=_env())
        assert sel.provider == "playwright_stealth"
        assert sel.available is True  # venv'de kurulu
        assert sel.kind == "page"
        assert sel.reason is None

    def test_invalid_value_falls_back_with_reason(self):
        sel = resolve_stealth(override="SuperStealth!99", env=_env())
        assert sel.provider == "playwright_stealth"  # sessiz YENİLİK yok: default
        assert sel.reason == "invalid_provider:SuperStealth!99"

    def test_none_is_available_noop(self):
        sel = resolve_stealth(override="none", env=_env())
        assert sel.provider == "none" and sel.available and sel.kind == "none"

    def test_invisible_without_binary_is_missing(self):
        sel = resolve_stealth(override="invisible", env=_env())
        assert sel.provider == "invisible"
        assert sel.available is False
        assert sel.reason == "binary_missing"

    def test_invisible_library_missing(self, monkeypatch):
        import agent_core.services.stealth_provider as sp
        monkeypatch.setattr(sp, "_lib_present", lambda n: False)
        sel = resolve_stealth(override="invisible", env=_env())
        assert sel.reason == "library_missing"

    def test_invisible_with_operator_binary_available(self, tmp_path):
        binary = tmp_path / "firefox-patched"
        binary.write_bytes(b"\x7fELF")
        sel = resolve_stealth(override="invisible",
                              env=_env(**{INVISIBLE_BINARY_ENV: str(binary)}))
        assert sel.available is True
        assert sel.kind == "launch"
        assert use_invisible_module(sel) is True
        assert browser_kind(sel) == "firefox"

    def test_cloak_requires_operator_binary(self, tmp_path):
        assert resolve_stealth(override="cloak", env=_env()).reason == "binary_missing"

        missing = tmp_path / "yok-dosya"
        sel = resolve_stealth(override="cloak",
                              env=_env(**{CLOAK_BINARY_ENV: str(missing)}))
        assert sel.reason == "binary_missing"  # var olmayan path dürüstçe red

        binary = tmp_path / "cloak-chrome"
        binary.write_bytes(b"\x7fELF")
        sel2 = resolve_stealth(override="cloak",
                               env=_env(**{CLOAK_BINARY_ENV: str(binary)}))
        assert sel2.available is True
        assert launch_overrides(sel2, env=_env(**{CLOAK_BINARY_ENV: str(binary)})) == {
            "executable_path": str(binary)}

    def test_launch_overrides_empty_for_default(self):
        sel = resolve_stealth(env=_env())
        assert launch_overrides(sel) == {}
        assert browser_kind(sel) == "chromium"


class TestApplyPageStealth:
    @pytest.mark.asyncio
    async def test_playwright_stealth_applies_init_scripts(self):
        calls = []

        class _FakePage:
            async def add_init_script(self, script=None, path=None):
                calls.append(script or "")

        from agent_core.services.stealth_provider import apply_page_stealth
        applied, note = await apply_page_stealth(resolve_stealth(env=_env()), _FakePage())
        assert applied is True
        assert note is None
        assert len(calls) > 0  # gerçek Stealth init-script'leri enjekte etti

    @pytest.mark.asyncio
    async def test_launch_level_provider_refused_honestly(self):
        from agent_core.services.stealth_provider import (
            StealthSelection,
            apply_page_stealth,
        )
        sel = StealthSelection(requested="invisible", provider="invisible",
                               available=True, reason=None, kind="launch")
        applied, note = await apply_page_stealth(sel, object())
        assert (applied, note) == (False, "launch_level_provider")

    @pytest.mark.asyncio
    async def test_unavailable_returns_reason(self):
        from agent_core.services.stealth_provider import apply_page_stealth
        sel = resolve_stealth(override="cloak", env=_env())
        applied, note = await apply_page_stealth(sel, object())
        assert applied is False and note == "binary_missing"

    @pytest.mark.asyncio
    async def test_none_is_noop(self):
        from agent_core.services.stealth_provider import apply_page_stealth
        applied, note = await apply_page_stealth(
            resolve_stealth(override="none", env=_env()), object())
        assert (applied, note) == (True, None)


class _LaunchRaises:
    async def launch(self, **kw):
        raise RuntimeError(
            "Executable doesn't exist at .../chromium-1234. "
            "Please run playwright install")


class _FakePlaywright:
    def __init__(self):
        self.chromium = _LaunchRaises()
        self.firefox = _LaunchRaises()


class _FakeAsyncPWFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        return _FakePlaywright()

    async def __aexit__(self, *exc):
        return False


def _inject_fake_playwright(monkeypatch):
    fake = types.ModuleType("playwright.async_api")
    fake.async_playwright = _FakeAsyncPWFactory()
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake)


class TestRegistryIntegration:
    @pytest.mark.asyncio
    async def test_default_emits_stealth_and_keeps_honest_launch_failure(self, monkeypatch):
        _inject_fake_playwright(monkeypatch)
        monkeypatch.delenv("STEALTH_PROVIDER", raising=False)
        logs = []

        def _log(level, msg):
            logs.append((level, msg))

        with pytest.raises(RuntimeError, match="Executable doesn't exist"):
            await scrape_instagram("https://instagram.com/alper", log=_log)
        assert any("STEALTH provider=playwright_stealth available=True" in m
                   for _, m in logs)

    @pytest.mark.asyncio
    async def test_unavailable_provider_degrades_honestly(self, monkeypatch):
        _inject_fake_playwright(monkeypatch)
        monkeypatch.setenv("STEALTH_PROVIDER", "invisible")  # binary yok
        logs = []

        async def run():
            await scrape_instagram("https://instagram.com/alper",
                                   log=lambda l, m: logs.append((l, m)))

        # invisible seçili ama binary yok: invisible modülüne GİRMEZ (import
        # edilmez), chromium yolu sürer ve launch dürüst şekilde patlar.
        import builtins
        real_import = builtins.__import__

        def _guard(name, *a, **kw):
            if name.startswith("invisible_playwright"):
                raise AssertionError("binary yokken invisible modülü import edilmemeli")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", _guard)
        with pytest.raises(RuntimeError, match="Executable doesn't exist"):
            await run()
        assert any("STEALTH provider=invisible available=False reason=binary_missing" in m
                   for _, m in logs)


class TestEndpoint:
    def test_endpoint_reports_selection(self, monkeypatch):
        monkeypatch.delenv("STEALTH_PROVIDER", raising=False)
        from backend.api import app
        with TestClient(app) as client:
            body = client.get("/api/experimental/stealth").json()
            assert body["provider"] == "playwright_stealth"
            assert body["available"] is True

            body = client.get("/api/experimental/stealth",
                              params={"provider": "invisible"}).json()
            assert body["provider"] == "invisible"
            assert body["available"] is False
            assert body["reason"] == "binary_missing"

            body = client.get("/api/experimental/stealth",
                              params={"provider": "bogus!!"}).json()
            assert body["provider"] == "playwright_stealth"
            assert body["reason"] == "invalid_provider:bogus!!"
