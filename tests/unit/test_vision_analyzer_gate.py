"""S2: vision_analyzer, LLMGateway uzerinden cagri yapar.

Kapilar:
  1) Basari yolu gateway.query(images=...) uzerinden ilerler; yanit
     VisualEvidence olarak ayristirilir. [015] fix: provider'in bildirdigi
     confidence GUVENILMEZ; forensik confidence yerel teminattan turetilir.
  2) LIVE_LLM_E2E=0 iken HICBIR outbound provider cagrisi olusmaz;
     sonuc UNAVAILABLE (fallback_reason='llm_unavailable').
  3) Bos/placeholder kanit ciktisi -> data_confidence=False (provider
     ne derse desin).
  4) Gateway hatasi UNAVAILABLE'a donusur (uydurma veri uretilmez).
"""


import pytest

from agent_core.services.llm_gateway import LLMGateway
from agent_core.services.vision_analyzer import VisionAnalyzer, VisualEvidence


class _FakeGateway:
    """Gateway arayuzunun kayit tutan sahte uygulamasi."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def query_json_chain(self, prompt, schema, **kwargs):
        self.calls.append((prompt, kwargs))
        resp = self.responses.pop(0)
        if isinstance(resp, str):
            raise ValueError(resp)
        return resp


@pytest.fixture
def fake_download(monkeypatch):
    async def _fake(self, url, client=None):
        return {
            "source_url": url,
            "status": "downloaded",
            "reason": "",
            "sha256": "ab" * 8,
            "mime": "image/jpeg",
            "bytes": 3,
            "b64": "QUJD",
        }

    monkeypatch.setattr(VisionAnalyzer, "_download_image_record", _fake)


@pytest.mark.asyncio
async def test_success_path_derives_confidence_locally(fake_download):
    """Provider confidence=0.9 beyan etse bile final confidence yerel
    teminattan turetilir ([015]): 1/1 indirme + 2/5 dolu kanit alani -> 0.7."""
    gw = _FakeGateway([
        VisualEvidence(
            detected_objects=["kitap"], aesthetic_style="minimal",
            confidence=0.99, data_confidence=True,  # provider'in beyani
        )
    ])
    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/a.jpg"])

    assert res.detected_objects == ["kitap"]
    assert res.confidence == pytest.approx(0.7), "yerel turetim (0.5*1 + 0.5*0.4)"
    assert res.data_confidence is True
    assert res.fallback_reason is None
    # [014] provenance tasiniyor
    assert len(res.image_provenance) == 1
    assert res.image_provenance[0]["source_url"] == "http://x/a.jpg"
    assert res.image_provenance[0]["status"] == "downloaded"

    assert len(gw.calls) == 1
    prompt, kwargs = gw.calls[0]
    assert kwargs["images"] == ["data:image/jpeg;base64,QUJD"]
    assert kwargs["temperature"] == 0.2
    # [012] fix: prompt'ta ornek/onerilen numeric confidence YOK
    assert '"confidence": 0.90' not in prompt
    assert "0.90" not in prompt


@pytest.mark.asyncio
async def test_no_outbound_call_when_live_gate_closed(fake_download, monkeypatch):
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)
    monkeypatch.delenv("USE_LOCAL_LLM", raising=False)

    gw = LLMGateway()
    gw.set_key("sk-test")  # unlock_live=False -> kapi kapali

    outbound = {"count": 0}

    class _Completions:
        async def create(self, **kw):
            outbound["count"] += 1
            raise AssertionError("outbound provider cagrisi yapilmamaliydi")

    gw.client = type("C", (), {"chat": type("CH", (), {"completions": _Completions()})()})()

    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/a.jpg"])

    assert outbound["count"] == 0, "LIVE_LLM_E2E=0 iken outbound cagri olustu"
    assert getattr(res, "data_confidence", False) is False
    assert getattr(res, "fallback_reason", "") == "llm_unavailable"
    assert res.confidence == 0.0
    assert res.detected_objects == []


@pytest.mark.asyncio
async def test_empty_provider_output_is_not_confident(fake_download):
    """Provider bos kanit dondurdu -> rich=0 -> confidence 0.5, data_confidence
    False ([015]: 'confidence': 0.7 beyani bile bos ciktiyi kurtaramaz)."""
    gw = _FakeGateway([
        VisualEvidence(detected_objects=[], confidence=0.7, data_confidence=True)
    ])
    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/a.jpg"])

    assert res.confidence == pytest.approx(0.5)  # 0.5*1 (indirme) + 0.5*0 (kanit)
    assert getattr(res, "data_confidence", True) is False
    assert res.fallback_reason == "empty_vision_output"


@pytest.mark.asyncio
async def test_gateway_error_returns_unavailable(fake_download):
    class _ErrGateway:
        async def query_json_chain(self, prompt, schema, **kwargs):
            raise RuntimeError("llm boom")

    va = VisionAnalyzer(_ErrGateway())
    res = await va.analyze_images(["http://x/a.jpg"])

    assert res.data_confidence is False
    assert res.fallback_reason == "llm_unavailable"
    assert res.confidence == 0.0


@pytest.mark.asyncio
async def test_partial_download_failure_keeps_provenance(monkeypatch):
    """[014]: 1 basarili + 1 basarisiz indirme -> hangi URL analiz edildi
    kaybolmaz; provenance her iki URL'yi de tasir."""
    outcomes = {
        "http://x/ok.jpg": {
            "source_url": "http://x/ok.jpg", "status": "downloaded",
            "reason": "", "sha256": "cd" * 8, "mime": "image/jpeg", "bytes": 3,
            "b64": "QUJD",
        },
        "http://x/bad.jpg": {
            "source_url": "http://x/bad.jpg", "status": "failed",
            "reason": "content_type_text/html", "sha256": None, "mime": None,
            "bytes": 0,
        },
    }

    async def _fake(self, url, client=None):
        return outcomes[url]

    monkeypatch.setattr(VisionAnalyzer, "_download_image_record", _fake)

    gw = _FakeGateway([
        VisualEvidence(
            detected_objects=["kitap"], environment_and_places=["kafe"],
            activity_signals=["okuma"],
            visual_evidence_summary="Kafede okuma.", aesthetic_style="loş",
        )
    ])
    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/ok.jpg", "http://x/bad.jpg"])

    assert len(res.image_provenance) == 2
    statuses = {p["source_url"]: p["status"] for p in res.image_provenance}
    assert statuses == {"http://x/ok.jpg": "downloaded", "http://x/bad.jpg": "failed"}
    # 1/2 indirme + 5/5 kanit -> 0.25 + 0.5 = 0.75
    assert res.confidence == pytest.approx(0.75)
    _, kwargs = gw.calls[0]
    assert len(kwargs["images"]) == 1, "basarisiz URL modele gonderilmez"
