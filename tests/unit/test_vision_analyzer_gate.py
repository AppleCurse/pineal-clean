"""S2: vision_analyzer, LLMGateway uzerinden cagri yapar.

Kapilar:
  1) Basari yolu gateway.query(images=...) uzerinden ilerler; yanit
     VisualEvidence olarak ayristirilir (data_confidence=True).
  2) LIVE_LLM_E2E=0 iken HICBIR outbound provider cagrisi olusmaz;
     sonuc UNAVAILABLE (fallback_reason='llm_live_gate_closed').
  3) Bozuk JSON tek tamir denemesi ile kurtarilir.
  4) Gateway hatasi UNAVAILABLE'a donusur (uydurma veri uretilmez).
"""

import json

import pytest

from agent_core.services.llm_gateway import LLMGateway
from agent_core.services.vision_analyzer import VisionAnalyzer


class _FakeGateway:
    """Gateway arayuzunun kayit tutan sahte uygulamasi."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.api_key = "sk-fake"

    async def query(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return self.responses.pop(0)

    @staticmethod
    def extract_json(text):
        return json.loads(text)


@pytest.fixture
def fake_download(monkeypatch):
    async def _fake(self, url):
        return "QUJD"

    monkeypatch.setattr(VisionAnalyzer, "_download_and_encode_image", _fake)


@pytest.mark.asyncio
async def test_success_path_uses_gateway_and_parses(fake_download):
    gw = _FakeGateway([
        json.dumps({"detected_objects": ["kitap"], "aesthetic_style": "minimal",
                    "confidence": 0.9}),
    ])
    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/a.jpg"])

    assert res.detected_objects == ["kitap"]
    assert res.confidence == 0.9
    assert res.data_confidence is True
    assert len(gw.calls) == 1
    _, kwargs = gw.calls[0]
    assert kwargs["images"] == ["data:image/jpeg;base64,QUJD"]
    assert kwargs["temperature"] == 0.2


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

    gw.client = type(
        "C", (), {"chat": type("CH", (), {"completions": _Completions()})()}
    )()

    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/a.jpg"])

    assert outbound["count"] == 0, "LIVE_LLM_E2E=0 iken outbound cagri olustu"
    assert res.data_confidence is False
    assert res.fallback_reason == "llm_live_gate_closed"
    assert res.confidence == 0.0
    assert res.detected_objects == []


@pytest.mark.asyncio
async def test_bad_json_triggers_single_repair(fake_download):
    gw = _FakeGateway([
        "bu json degil",
        json.dumps({"detected_objects": [], "confidence": 0.7}),
    ])
    va = VisionAnalyzer(gw)
    res = await va.analyze_images(["http://x/a.jpg"])

    assert res.confidence == 0.7
    assert res.data_confidence is True
    assert len(gw.calls) == 2, "tamir icin tam olarak bir ek cagri beklenir"


@pytest.mark.asyncio
async def test_gateway_error_returns_unavailable(fake_download):
    class _ErrGateway:
        api_key = "sk-fake"

        async def query(self, prompt, **kwargs):
            raise RuntimeError("llm boom")

        @staticmethod
        def extract_json(text):
            raise ValueError("n/a")

    va = VisionAnalyzer(_ErrGateway())
    res = await va.analyze_images(["http://x/a.jpg"])

    assert res.data_confidence is False
    assert res.fallback_reason == "llm_unavailable"
    assert res.confidence == 0.0
