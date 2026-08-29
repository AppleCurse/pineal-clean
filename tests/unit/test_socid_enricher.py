"""socid-extractor entegrasyon sözleşme testleri.

İlkeler (projenin dürüstlük sözleşmesiyle hizalı):
- Kütüphane kayıt çıkaramazsa `available=False` + makine-okunur sebep.
- Alan ASLA uydurulmaz.
- SSRF guard: private/loopback URL'ler engellenir.
- Public-web araştırma zenginleştirmesi asıl sonucu bozmaz.
"""
import pytest
from unittest.mock import AsyncMock, patch

from agent_core.services import socid_enricher
from agent_core.services.socid_enricher import (
    SocidRecord,
    extract_from_html,
    extract_profile,
)


def _fake_extract(fields_by_text):
    """socid_extractor.extract'i metne göre taklit eden fabrika."""
    def _extract(text):
        return fields_by_text.get(text, {})
    return _extract


class TestExtractFromHtml:
    def test_returns_available_record_when_fields_found(self, monkeypatch):
        monkeypatch.setattr(
            "socid_extractor.extract", _fake_extract({"<html>x</html>": {"username": "muse"}})
        )
        rec = extract_from_html("<html>x</html>", source_url="https://example.com/u")
        assert rec.available is True
        assert rec.fields == {"username": "muse"}
        assert rec.provider == "socid_extractor"
        assert rec.reason is None

    def test_returns_no_record_for_unrecognized_page(self, monkeypatch):
        monkeypatch.setattr("socid_extractor.extract", _fake_extract({}))
        rec = extract_from_html("<html>login wall</html>", source_url="https://example.com/u")
        assert rec.available is False
        assert rec.reason == "no_record"
        assert rec.fields == {}

    def test_tuple_return_normalized(self, monkeypatch):
        """Bazı socid_extractor sürümleri (dict, flags) tuple döner."""
        def _tuple_extract(text):
            return ({"GAIA_ID": "123"}, ["flag"])
        monkeypatch.setattr("socid_extractor.extract", _tuple_extract)
        rec = extract_from_html("<html>y</html>", source_url="https://example.com/g")
        assert rec.available is True
        assert rec.fields == {"GAIA_ID": "123"}

    def test_library_missing_is_honest(self):
        from unittest.mock import patch
        with patch.dict("sys.modules", {"socid_extractor": None}):
            rec = extract_from_html("<html>x</html>", source_url="https://example.com/u")
        assert rec.available is False
        assert rec.reason == "library_missing"


class TestExtractProfile:
    @pytest.mark.asyncio
    async def test_invalid_url_rejected(self):
        rec = await extract_profile("not-a-url")
        assert rec.available is False
        assert rec.reason == "invalid_url"

    @pytest.mark.asyncio
    async def test_ssrf_blocked(self):
        rec = await extract_profile("http://127.0.0.1:8000/secret")
        assert rec.available is False
        assert rec.reason == "ssrf_blocked"

    @pytest.mark.asyncio
    async def test_network_error_is_honest(self):
        rec = await extract_profile("https://example-invalid-host-xyz.test/u")
        assert rec.available is False
        assert rec.reason in ("network_error", "ssrf_blocked")


class TestEnrichUrls:
    @pytest.mark.asyncio
    async def test_enrich_returns_only_available(self, monkeypatch):
        async def _fake_extract_profile(url, client=None):
            if url.endswith("/good"):
                return SocidRecord(source_url=url, available=True, fields={"pk": "1"})
            return SocidRecord(source_url=url, available=False, reason="no_record")

        monkeypatch.setattr(socid_enricher, "extract_profile", _fake_extract_profile)
        out = await socid_enricher.enrich_urls(
            ["https://x.test/a/good", "https://x.test/b/bad", "https://x.test/c/good"]
        )
        assert [r.source_url for r in out] == ["https://x.test/a/good", "https://x.test/c/good"]

    @pytest.mark.asyncio
    async def test_enrich_respects_limit(self, monkeypatch):
        calls = []

        async def _fake(url, client=None):
            calls.append(url)
            return SocidRecord(source_url=url, available=True, fields={})

        monkeypatch.setattr(socid_enricher, "extract_profile", _fake)
        await socid_enricher.enrich_urls(["https://a.test/1", "https://a.test/2", "https://a.test/3", "https://a.test/4"], limit=2)
        assert len(calls) == 2


class TestPublicWebResearchIntegration:
    @pytest.mark.asyncio
    async def test_research_enrichment_adds_socid_and_never_breaks_contract(self):
        """_run_public_web_research: eşleşen sonuca socid alanı eklenir; kütüphane
        bulunamazsa/ağ yoksa sonuç alanları AYNI kalır (sözleşme bozulmaz)."""
        from backend.api import _run_public_web_research
        from agent_core.services.search_engine import SearchOutcome, SearchResult

        outcome = SearchOutcome(
            results=[SearchResult(query='"hedef"', content="hedef profili", source_url="https://site.test/hedef", provider="ddg")],
            status="OK", available=True,
        )
        search = type("S", (), {"search": AsyncMock(return_value=outcome)})()

        record = SocidRecord(source_url="https://site.test/hedef", available=True, fields={"uid": "42"})
        with patch("agent_core.services.socid_enricher.enrich_urls", AsyncMock(return_value=[record])):
            res = await _run_public_web_research("https://x.com/hedef", search)

        assert res["status"] == "ok"
        assert res["results"][0]["socid"]["fields"] == {"uid": "42"}
        assert "kimlik kaydı" in res["note"]

    @pytest.mark.asyncio
    async def test_research_enrichment_failure_keeps_contract(self):
        from backend.api import _run_public_web_research
        from agent_core.services.search_engine import SearchOutcome, SearchResult

        outcome = SearchOutcome(
            results=[SearchResult(query='"hedef"', content="hedef", source_url="https://site.test/hedef", provider="ddg")],
            status="OK", available=True,
        )
        search = type("S", (), {"search": AsyncMock(return_value=outcome)})()

        with patch("agent_core.services.socid_enricher.enrich_urls", AsyncMock(side_effect=ImportError("no lib"))):
            res = await _run_public_web_research("https://x.com/hedef", search)

        assert res["status"] == "ok"
        assert "socid" not in res["results"][0]  # alan eklenmedi, sözleşme bozulmadı
