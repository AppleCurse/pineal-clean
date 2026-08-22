"""
FAZ 5 / G5.1 — LLM protokol E2E: GERÇEK LLMGateway kod yolu, sahte HTTP katmanı.

Fark (test illüzyonuna karşı): query() mock'lanmaz; AsyncOpenAI istemcisi
httpx.MockTransport'a bağlanır — retry, 429 backoff, 401 reddi, circuit breaker
ve query_json'ın HTTP→extract_json→schema zinciri GERÇEK kodda koşar.
"""
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_core.services.llm_gateway import LLMGateway


def _gateway_with_mock(handler) -> LLMGateway:
    gw = LLMGateway()
    gw.set_key("sk-or-v1-protocol-test")
    gw.client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-v1-protocol-test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return gw


def _ok_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}}]
    })


class _Probe(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_retry_on_429_then_success(monkeypatch):
    """429 → backoff → başarı: istemci 2 istek atar, çağrı ölmez (gerçek retry yolu)."""
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return _ok_response("ikinci denemede geldi")

    gw = _gateway_with_mock(handler)
    res = await gw.query("ping", tier=1)
    assert res == "ikinci denemede geldi"
    assert calls["n"] == 2, "429 sonrası tek retry beklenir"


@pytest.mark.asyncio
async def test_auth_error_rejected_immediately(monkeypatch):
    """401: retry YOK, anında RuntimeError('LLM API Key rejected')."""
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "invalid_api_key"}})

    gw = _gateway_with_mock(handler)
    with pytest.raises(RuntimeError, match="LLM API Key rejected"):
        await gw.query("ping")
    assert calls["n"] == 1, "auth hatası retry edilmemeli"


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(monkeypatch):
    """5+ başarısızlık → devre açılır; sonraki çağrı HTTP'e hiç gitmeden reddedilir."""
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": {"message": "boom"}})

    gw = _gateway_with_mock(handler)
    gw.failure_count = 5  # sınırdayız
    with pytest.raises(Exception):
        await gw.query("ping")
    assert gw.circuit_open is True
    calls_before = calls["n"]  # SDK'nin kendi 5xx retry'i dahil

    with pytest.raises(RuntimeError, match="Circuit breaker"):
        await gw.query("ping")
    assert calls["n"] == calls_before, "devre açıkken YENİ HTTP isteği gitmemeli"


@pytest.mark.asyncio
async def test_query_json_full_http_path_with_markdown_fence(monkeypatch):
    """HTTP → markdown-fenced JSON → extract_json → pydantic: uçtan uca gerçek zincir."""
    monkeypatch.setenv("LIVE_LLM_E2E", "1")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        user_content = body["messages"][-1]["content"]
        assert "Probe" in user_content or "answer" in user_content  # şema prompt'a gömülü
        return _ok_response('```json\n{"answer": "42"}\n```')

    gw = _gateway_with_mock(handler)
    res = await gw.query_json("Cevabı ver", _Probe, tier=2)
    assert isinstance(res, _Probe)
    assert res.answer == "42"
