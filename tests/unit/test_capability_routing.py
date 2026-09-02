"""Capability-based routing bridge: agent JSON chains → UnifiedRouter.

Covers:
- ``required_capabilities`` task/agent mapping,
- catalog capability filtering of legacy chains (drop known-incompatible, keep unknown),
- ``RoutedChatExecutor.model_groups_for_capabilities`` selection,
- end-to-end ``query_json_chain`` through the unified router (hermetic local provider),
- fail-safe default (legacy path when the unified backend is not opted in).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_core.services.llm_gateway import LLMGateway
from agent_core.services.routed_chat import RoutedChatExecutor

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = REPO_ROOT / "config" / "router.example.json"


class _Probe(BaseModel):
    value: str


def _gateway() -> LLMGateway:
    gateway = LLMGateway()
    gateway.cache = None
    return gateway


def _local_config() -> dict:
    return {
        "schema_version": 1,
        "tenant_id": "t",
        "connections": [
            {
                "id": "ollama",
                "provider_id": "ollama-local",
                "connection_type": "local",
                "enabled": True,
            },
        ],
        "model_groups": {"local": ["ollama-local/llama3.2"]},
    }


def _cloud_config() -> dict:
    return {
        "schema_version": 1,
        "tenant_id": "t",
        "connections": [
            {
                "id": "or",
                "provider_id": "openrouter",
                "connection_type": "api_key",
                "credential_env": "OPENROUTER_API_KEY",
                "enabled": True,
            },
        ],
        "model_groups": {
            "vision": ["openrouter/google/gemini-3.7-flash"],
            "chat": ["openrouter/upstage/solar-pro4"],
        },
    }


# ---------------------------------------------------------------- capabilities

def test_required_capabilities_mapping():
    gateway = _gateway()
    assert gateway.required_capabilities("vision") == frozenset({"chat", "vision"})
    assert gateway.required_capabilities("depth", "vision_analyzer") == frozenset({"chat", "vision"})
    assert gateway.required_capabilities("depth") == frozenset({"chat"})
    assert gateway.required_capabilities("bogus") == frozenset({"chat"})


def test_capability_filter_drops_known_incompatible_models():
    gateway = _gateway()
    chain = ["upstage/solar-pro4", "google/gemini-3.7-flash"]
    filtered = gateway._capability_filter_chain(chain, frozenset({"chat", "vision"}))
    assert filtered == ["google/gemini-3.7-flash"]


def test_capability_filter_keeps_unknown_models():
    gateway = _gateway()
    chain = ["upstage/solar-pro4", "custom/private-model"]
    filtered = gateway._capability_filter_chain(chain, frozenset({"chat", "vision"}))
    # custom/private-model is passthrough/unknown → kept; solar-pro4 is dropped.
    assert filtered == ["custom/private-model"]


# ---------------------------------------------------------------- group selection

def test_model_groups_for_capabilities_selects_only_vision_group(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    executor = RoutedChatExecutor.from_mapping(_cloud_config())
    gateway = _gateway()
    gateway.live_unlocked = True

    vision_groups = executor.model_groups_for_capabilities(gateway, {"chat", "vision"})
    assert vision_groups == ("vision",)

    chat_groups = executor.model_groups_for_capabilities(gateway, {"chat"})
    assert chat_groups == ("vision", "chat")


def test_model_groups_for_capabilities_no_match_is_empty(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    executor = RoutedChatExecutor.from_mapping(_cloud_config())
    gateway = _gateway()
    gateway.live_unlocked = True
    assert executor.model_groups_for_capabilities(gateway, {"audio_input"}) == ()


# ---------------------------------------------------------------- env fail-safe

def test_routed_executor_from_env_defaults_to_none(monkeypatch):
    monkeypatch.delenv("PINEAL_LLM_BACKEND", raising=False)
    monkeypatch.delenv("PINEAL_ROUTER_CONFIG", raising=False)
    assert _gateway()._routed_executor_from_env() is None


def test_routed_executor_from_env_unified_without_config_is_none(monkeypatch):
    monkeypatch.setenv("PINEAL_LLM_BACKEND", "unified")
    monkeypatch.delenv("PINEAL_ROUTER_CONFIG", raising=False)
    assert _gateway()._routed_executor_from_env() is None


def test_routed_executor_from_env_unified_with_config_resolves(monkeypatch):
    monkeypatch.setenv("PINEAL_LLM_BACKEND", "unified")
    monkeypatch.setenv("PINEAL_ROUTER_CONFIG", str(EXAMPLE_CONFIG))
    executor = _gateway()._routed_executor_from_env()
    assert executor is not None
    assert executor.handles("local") is True


# ---------------------------------------------------------------- end-to-end routed query

@pytest.mark.asyncio
async def test_query_json_chain_routes_through_executor(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-local-1",
                "object": "chat.completion",
                "created": 1_800_000_000,
                "model": "llama3.2",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps({"value": "routed-ok"})},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    gateway = _gateway()
    gateway.attach_routed_executor(RoutedChatExecutor.from_mapping(_local_config()))

    mock_client = AsyncOpenAI(
        base_url="http://127.0.0.1:11434/v1",
        api_key="not-needed",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    gateway._client_for_route = lambda route: mock_client

    result = await gateway.query_json_chain(
        "Return the value.",
        schema=_Probe,
        task="depth",
    )

    assert result == _Probe(value="routed-ok")
    assert captured["model"] == "llama3.2"
    # Provider ownership stays in the gateway: one call record under the routed provider.
    assert gateway.call_log[-1]["provider"] == "ollama-local"


@pytest.mark.asyncio
async def test_query_json_chain_routed_no_capable_group_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    gateway = _gateway()
    gateway.live_unlocked = True
    # No vision-capable model anywhere: the {chat, vision} requirement cannot be
    # satisfied, so the routed path must refuse before any network attempt.
    executor = RoutedChatExecutor.from_mapping(
        {
            "schema_version": 1,
            "tenant_id": "t",
            "connections": [
                {
                    "id": "or",
                    "provider_id": "openrouter",
                    "connection_type": "api_key",
                    "credential_env": "OPENROUTER_API_KEY",
                    "enabled": True,
                },
            ],
            "model_groups": {"chat": ["openrouter/upstage/solar-pro4"]},
        }
    )
    gateway.attach_routed_executor(executor)

    with pytest.raises(RuntimeError, match="ROUTE_UNAVAILABLE"):
        await gateway.query_json_chain(
            "Return the value.",
            schema=_Probe,
            task="depth",
            agent_name="vision_analyzer",  # forces {chat, vision}
        )


@pytest.mark.asyncio
async def test_query_json_chain_legacy_path_without_executor(monkeypatch):
    """Without the unified backend, the legacy chain path stays the default."""
    monkeypatch.delenv("PINEAL_LLM_BACKEND", raising=False)
    monkeypatch.delenv("PINEAL_ROUTER_CONFIG", raising=False)
    gateway = _gateway()
    # Legacy path is attempted (and stops honestly at the live-LLM gate) rather
    # than taking the routed path.
    with pytest.raises(RuntimeError, match="REAL_LLM_CALL_NOT_EXECUTED"):
        await gateway.query_json_chain("Return the value.", schema=_Probe, task="depth")