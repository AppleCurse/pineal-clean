"""OpenAI client surface through the real gateway and a hermetic HTTP transport."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

import backend.api as api_module
from agent_core.services.llm_gateway import LLMGateway, SpendCapExceeded
from backend.api import app


def _gateway(handler) -> LLMGateway:
    gateway = LLMGateway()
    gateway.set_key("provider-test-key", unlock_live=True)
    gateway.client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="provider-test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    return gateway


def _completion_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-upstream-1",
            "object": "chat.completion",
            "created": 1_800_000_000,
            "model": "upstage/solar-pro4",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-weather",
                                "type": "function",
                                "function": {
                                    "name": "weather",
                                    "arguments": '{"city":"Istanbul"}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
            },
        },
    )


def test_chat_completions_preserves_messages_tools_accounting_and_call_identity(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return _completion_response()

    gateway = _gateway(handler)
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    monkeypatch.delenv("PINEAL_TOKEN", raising=False)
    payload = {
        "model": "solar_pro4",
        "messages": [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Weather?"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "max_completion_tokens": 128,
    }

    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "weather"
    assert captured["body"]["messages"] == payload["messages"]
    assert captured["body"]["tools"] == payload["tools"]
    assert captured["body"]["max_tokens"] == 128
    assert captured["body"]["model"] == "upstage/solar-pro4"
    assert captured["authorization"] == "Bearer provider-test-key"

    call_id = response.headers["x-pineal-call-id"]
    assert len(call_id) == 36
    assert len(gateway.call_log) == 1
    assert gateway.call_log[0]["call_id"] == call_id
    assert gateway.call_log[0]["kind"] == "chat.completions"
    assert gateway.call_log[0]["task_id"].startswith("op_")
    assert gateway.call_log[0]["prompt_tokens"] == 100
    assert gateway.budget_status()["active_reservations"] == 0
    assert gateway.spend_usd > 0
    assert response.headers["x-pineal-optimization-mode"] == "disabled"
    assert response.headers["x-pineal-optimization-bytes-saved"] == "0"
    assert response.headers["x-pineal-optimization-lossy"] == "false"


def test_safe_tool_optimization_is_exactly_reported_and_preserves_non_tool_fields(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response()

    gateway = _gateway(handler)
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    pretty_tool_json = (
        "\x1b[31m"
        + json.dumps(
            {"records": [{"id": index, "value": "x" * 30} for index in range(20)]},
            indent=2,
        )
        + "\x1b[0m"
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    messages = [
        {"role": "system", "content": "Keep this spacing exactly."},
        {"role": "user", "content": "Do not rewrite me."},
        {"role": "tool", "tool_call_id": "call-1", "content": pretty_tool_json},
    ]

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-Pineal-Tool-Optimization": "safe"},
            json={"model": "solar_pro4", "messages": messages, "tools": tools},
        )

    assert response.status_code == 200
    forwarded = captured["body"]
    assert forwarded["messages"][:2] == messages[:2]
    assert forwarded["tools"] == tools
    assert "\x1b" not in forwarded["messages"][2]["content"]
    assert "\n" not in forwarded["messages"][2]["content"]
    assert response.headers["x-pineal-optimization-mode"] == "safe"
    assert int(response.headers["x-pineal-optimization-bytes-saved"]) > 0
    assert response.headers["x-pineal-optimization-lossy"] == "false"


def test_lossy_mode_still_preserves_fenced_code_and_reports_no_loss(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response()

    gateway = _gateway(handler)
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    fenced_code = "```python\n" + "print('must remain exact')\n" * 500 + "```"

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-Pineal-Tool-Optimization": "lossy"},
            json={
                "model": "solar_pro4",
                "messages": [{"role": "tool", "tool_call_id": "call-1", "content": fenced_code}],
            },
        )

    assert response.status_code == 200
    assert captured["body"]["messages"][0]["content"] == fenced_code
    assert response.headers["x-pineal-optimization-mode"] == "lossy"
    assert response.headers["x-pineal-optimization-lossy"] == "false"


def test_lossy_tool_optimization_requires_opt_in_and_marks_the_response(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response()

    gateway = _gateway(handler)
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    repeated_output = "still running\n" * 40

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-Pineal-Tool-Optimization": "lossy"},
            json={
                "model": "solar_pro4",
                "messages": [
                    {
                        "role": "tool",
                        "tool_call_id": "call-1",
                        "content": repeated_output,
                    }
                ],
            },
        )

    assert response.status_code == 200
    output = captured["body"]["messages"][0]["content"]
    assert "previous line repeated 39 times" in output
    assert response.headers["x-pineal-optimization-lossy"] == "true"
    assert int(response.headers["x-pineal-optimization-bytes-saved"]) > 0


@pytest.mark.asyncio
async def test_official_openai_sdk_accepts_pineal_as_custom_base_url(monkeypatch):
    gateway = _gateway(lambda request: _completion_response())
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    monkeypatch.delenv("PINEAL_TOKEN", raising=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://pineal.test") as http_client:
        client = AsyncOpenAI(
            base_url="http://pineal.test/v1",
            api_key="inbound-development-key",
            http_client=http_client,
        )
        response = await client.chat.completions.create(
            model="solar_pro4",
            messages=[{"role": "user", "content": "Use the custom base URL"}],
        )

    assert response.id == "chatcmpl-upstream-1"
    assert response.choices[0].message.tool_calls[0].function.name == "weather"
    assert gateway.call_log[-1]["provider"] == "openrouter"


def test_v1_bearer_auth_is_separate_from_provider_credentials(monkeypatch):
    inbound_token = "pineal-inbound-token-with-sufficient-length"
    seen_authorization: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_authorization.append(request.headers.get("authorization"))
        return _completion_response()

    gateway = _gateway(handler)
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    monkeypatch.setenv("PINEAL_TOKEN", inbound_token)

    with TestClient(app) as client:
        missing = client.post(
            "/v1/chat/completions",
            json={"model": "solar_pro4", "messages": [{"role": "user", "content": "hi"}]},
        )
        accepted = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {inbound_token}"},
            json={"model": "solar_pro4", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert missing.status_code == 401
    assert missing.json()["error"]["type"] == "authentication_error"
    assert accepted.status_code == 200
    assert seen_authorization == ["Bearer provider-test-key"]
    assert inbound_token not in repr(gateway.call_log)


def test_streaming_is_rejected_honestly_before_provider_execution(monkeypatch):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _completion_response()

    gateway = _gateway(handler)
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    monkeypatch.delenv("PINEAL_TOKEN", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "solar_pro4",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "streaming_not_supported"
    assert calls == 0
    assert gateway.call_log == []


def test_models_lists_only_currently_executable_gateway_models(monkeypatch):
    gateway = LLMGateway()
    gateway.live_unlocked = False
    gateway.use_local = False
    monkeypatch.setattr(api_module, "_openai_gateway", lambda: gateway)
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)
    monkeypatch.delenv("PINEAL_TOKEN", raising=False)

    with TestClient(app) as client:
        locked = client.get("/v1/models")
        gateway.set_key("provider-test-key", unlock_live=True)
        enabled = client.get("/v1/models")

    assert locked.status_code == 200
    assert locked.json() == {"object": "list", "data": []}
    listed = {model["id"] for model in enabled.json()["data"]}
    assert "upstage/solar-pro4" in listed
    assert all(model["object"] == "model" for model in enabled.json()["data"])


@pytest.mark.asyncio
async def test_gateway_retries_only_known_transient_errors():
    class UnknownFailure(Exception):
        pass

    gateway = LLMGateway()
    gateway.set_key("provider-test-key", unlock_live=True)

    class Completions:
        attempts = 0

        async def create(self, **kwargs):
            self.attempts += 1
            raise UnknownFailure("vendor-specific terminal failure")

    completions = Completions()
    gateway.client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": completions})()},
    )()

    with pytest.raises(UnknownFailure):
        await gateway.chat_completion(
            model="upstage/solar-pro4",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert completions.attempts == 1
    assert gateway.call_log[-1]["error"] == "UnknownFailure"


@pytest.mark.asyncio
async def test_chat_cancellation_releases_spend_reservation():
    gateway = LLMGateway()
    gateway.set_key("provider-test-key", unlock_live=True)
    gateway.spend_cap_usd = 1.0

    class Completions:
        async def create(self, **kwargs):
            raise asyncio.CancelledError()

    gateway.client = SimpleNamespace(
        chat=SimpleNamespace(completions=Completions()),
    )
    with pytest.raises(asyncio.CancelledError):
        await gateway.chat_completion(
            model="upstage/solar-pro4",
            messages=[{"role": "user", "content": "cancel"}],
            max_tokens=100,
        )

    assert gateway.budget_status()["active_reservations"] == 0
    assert gateway.budget_status()["reserved_usd"] == 0
    assert gateway.call_log[-1]["error"] == "CANCELLED"


@pytest.mark.asyncio
async def test_concurrent_chat_requests_cannot_overbook_spend_cap():
    gateway = LLMGateway()
    gateway.set_key("provider-test-key", unlock_live=True)
    messages = [{"role": "user", "content": "bounded"}]
    request_payload = {
        "model": "upstage/solar-pro4",
        "messages": messages,
        "max_tokens": 100,
    }
    reservation = gateway._maximum_chat_cost(  # noqa: SLF001 - exact cap regression
        "upstage/solar-pro4",
        request_payload,
        100,
    )
    gateway.spend_cap_usd = reservation * 1.5
    entered = asyncio.Event()
    release = asyncio.Event()

    class Completions:
        calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            entered.set()
            await release.wait()
            usage = SimpleNamespace(prompt_tokens=10, completion_tokens=10)
            return SimpleNamespace(usage=usage)

    completions = Completions()
    gateway.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    first = asyncio.create_task(
        gateway.chat_completion(
            model="upstage/solar-pro4",
            messages=messages,
            max_tokens=100,
        )
    )
    await entered.wait()
    with pytest.raises(SpendCapExceeded):
        await gateway.chat_completion(
            model="upstage/solar-pro4",
            messages=messages,
            max_tokens=100,
        )
    release.set()
    first_result = await first

    assert first_result.call_id
    assert completions.calls == 1
    assert gateway.budget_status()["active_reservations"] == 0
    assert len({record["call_id"] for record in gateway.call_log}) == 2
