"""
FAZ 3 / G3.5 — LLMGateway vision (multimodal) sözleşmesi.

Gerçek query() kod yolu, sahte OpenAI istemcisi ile: LIVE_LLM_E2E kapısı,
vision model seçimi ve multimodal content yapısı kanıtlanır.
"""
import pytest

from agent_core.services.llm_gateway import LLMGateway


class _FakeMsg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeChoice:
    def __init__(self, content):
        self.choices = [_FakeMsg(content)]


class _FakeCompletions:
    def __init__(self, content="ok"):
        self.content = content
        self.captured = None

    async def create(self, **kwargs):
        self.captured = kwargs
        return _FakeChoice(self.content)


@pytest.mark.asyncio
async def test_images_use_vision_model_and_multimodal_content(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    gw = LLMGateway()
    gw.set_key("sk-or-v1-test")
    fake = _FakeCompletions("görsel analizi: dağ manzarası")
    gw.client = type("C", (), {"chat": type("CH", (), {"completions": fake})()})()

    img = "data:image/png;base64,AAAA"
    res = await gw.query("Bu görselde ne var?", images=[img])

    assert res == "görsel analizi: dağ manzarası"
    model = fake.captured["model"]
    assert model == LLMGateway.DEFAULT_VISION_MODEL, "görselli istek vision modeline gitmeli"
    user_msg = fake.captured["messages"][-1]
    assert isinstance(user_msg["content"], list), "multimodal content listesi olmalı"
    types = [c["type"] for c in user_msg["content"]]
    assert types == ["text", "image_url"]
    assert user_msg["content"][1]["image_url"]["url"] == img


@pytest.mark.asyncio
async def test_explicit_model_wins_over_vision_default(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    gw = LLMGateway()
    gw.set_key("sk-or-v1-test")
    fake = _FakeCompletions()
    gw.client = type("C", (), {"chat": type("CH", (), {"completions": fake})()})()

    await gw.query("prompt", model="deepseek/deepseek-v4-flash",
                   images=["data:image/png;base64,BB"])
    assert fake.captured["model"] == "deepseek/deepseek-v4-flash"


@pytest.mark.asyncio
async def test_no_images_keeps_plain_text_content(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    gw = LLMGateway()
    gw.set_key("sk-or-v1-test")
    fake = _FakeCompletions()
    gw.client = type("C", (), {"chat": type("CH", (), {"completions": fake})()})()

    await gw.query("sadece metin")
    user_msg = fake.captured["messages"][-1]
    assert isinstance(user_msg["content"], str), "görselsiz istek düz metin kalmalı"
    assert fake.captured["model"] == LLMGateway.TIER_1_MODEL


@pytest.mark.asyncio
async def test_query_chain_skips_text_only_models_when_images_are_present(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    gw = LLMGateway()
    gw.set_key("sk-or-v1-test")
    fake = _FakeCompletions("görsel")
    gw.client = type("C", (), {"chat": type("CH", (), {"completions": fake})()})()

    result = await gw.query_chain("Bu görselde ne var?", task="vision", images=["data:image/png;base64,AA"])
    assert result == "görsel"
    assert fake.captured["model"] == "google/gemini-3.7-flash"


@pytest.mark.asyncio
async def test_vision_guard_respects_live_llm_gate(monkeypatch):
    """Görselli istek de güvenlik kapısını aşamaz (LIVE_LLM_E2E=0 -> RED)."""
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)
    gw = LLMGateway()
    gw.set_key("sk-or-v1-test")
    with pytest.raises(RuntimeError, match="REAL_LLM_CALL_NOT_EXECUTED"):
        await gw.query("prompt", images=["data:image/png;base64,AA"])
