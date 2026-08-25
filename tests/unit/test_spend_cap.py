"""OPENROUTER_MAX_SPEND_USD sert tavanı."""

import pytest
from unittest.mock import AsyncMock

from agent_core.services.llm_gateway import LLMGateway, SpendCapExceeded


class _Usage:
    prompt_tokens = 1_000_000
    completion_tokens = 0


class _Resp:
    usage = _Usage()
    choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]


@pytest.mark.asyncio
async def test_spend_cap_blocks_after_threshold(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "0.02")
    monkeypatch.delenv("USE_LOCAL_LLM", raising=False)
    gw = LLMGateway()
    gw.set_key("sk-test", unlock_live=True)
    gw.cache = None
    gw.max_spend_usd = 0.02

    create = AsyncMock(return_value=_Resp())
    gw.client = type("C", (), {"chat": type("CH", (), {"completions": type("Co", (), {"create": create})()})()})()

    await gw.query("p1", model="upstage/solar-pro4")
    assert gw.total_cost > 0
    with pytest.raises(SpendCapExceeded):
        await gw.query("p2", model="upstage/solar-pro4")
    assert create.await_count == 1


@pytest.mark.asyncio
async def test_spend_cap_disabled_when_zero(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "0")
    gw = LLMGateway()
    gw.set_key("sk-test", unlock_live=True)
    gw.cache = None
    gw.max_spend_usd = 0.0
    gw.total_cost = 99.0
    create = AsyncMock(return_value=_Resp())
    gw.client = type("C", (), {"chat": type("CH", (), {"completions": type("Co", (), {"create": create})()})()})()
    assert await gw.query("p", model="upstage/solar-pro4") == "ok"
