"""Streaming spend settlement: exactly-once, reservation retention, degradation."""

from types import SimpleNamespace

import pytest

from agent_core.services.llm_gateway import GatewayRoute, LLMGateway


def _route(**overrides) -> GatewayRoute:
    kwargs = dict(
        connection_id="nous-default",
        provider_id="nous-research",
        model="stepfun/step-3.7-flash",
        base_url="https://inference-api.nousresearch.com/v1",
        api_key="nk-test",
        local=False,
        input_per_million_usd=0.20,
        output_per_million_usd=1.15,
    )
    kwargs.update(overrides)
    return GatewayRoute(**kwargs)


def _gateway(monkeypatch, upstream_factory) -> tuple[LLMGateway, dict]:
    gateway = LLMGateway()
    gateway.set_key("nk-test", unlock_live=True)
    gateway.cache = None
    state = {"calls": 0}

    class Completions:
        async def create(self, **kwargs):
            state["calls"] += 1
            return upstream_factory()

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=Completions()),
    )
    monkeypatch.setattr(gateway, "_client_for_route", lambda route: fake_client)
    return gateway, state


def _chunk(usage=None, content="tok"):
    return SimpleNamespace(usage=usage, choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


def _messages():
    return [{"role": "user", "content": "stream me"}]


@pytest.mark.asyncio
async def test_normal_completion_settles_exactly_once(monkeypatch):
    async def upstream():
        yield _chunk(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))

    gateway, _ = _gateway(monkeypatch, upstream)
    stream = await gateway.start_chat_stream(
        messages=_messages(),
        model="stepfun/step-3.7-flash",
        route=_route(),
    )
    chunks = [chunk async for chunk in stream.chunks]
    assert len(chunks) == 1

    assert gateway.budget_status()["active_reservations"] == 0
    expected = (10 * 0.20 + 5 * 1.15) / 1_000_000
    assert gateway.spend_usd == pytest.approx(expected)
    # Exactly one logical record, settled (no error).
    records = [r for r in gateway.call_log if r["kind"] == "chat.completions.stream"]
    assert len(records) == 1
    assert records[0]["error"] is None
    assert records[0]["cost_usd"] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_missing_usage_retains_full_reservation(monkeypatch):
    async def upstream():
        yield _chunk(usage=None)

    gateway, _ = _gateway(monkeypatch, upstream)
    before = gateway.budget_status()["reserved_usd"]
    stream = await gateway.start_chat_stream(
        messages=_messages(),
        model="stepfun/step-3.7-flash",
        route=_route(),
    )
    # reservation is made before the first chunk is returned
    assert gateway.budget_status()["active_reservations"] == 1
    [chunk async for chunk in stream.chunks]

    assert gateway.budget_status()["active_reservations"] == 0
    # Missing usage must NOT zero the cost: the full reservation is retained.
    assert gateway.spend_usd > 0.0
    records = [r for r in gateway.call_log if r["kind"] == "chat.completions.stream"]
    assert records[-1]["prompt_tokens"] is None
    assert records[-1]["cost_usd"] > 0.0


@pytest.mark.asyncio
async def test_interruption_marks_stream_and_preserves_reservation(monkeypatch):
    async def upstream():
        yield _chunk(usage=None)
        raise RuntimeError("connection reset by peer")

    gateway, _ = _gateway(monkeypatch, upstream)
    stream = await gateway.start_chat_stream(
        messages=_messages(),
        model="stepfun/step-3.7-flash",
        route=_route(),
    )
    with pytest.raises(RuntimeError, match="connection reset"):
        [chunk async for chunk in stream.chunks]

    assert gateway.budget_status()["active_reservations"] == 0
    records = [r for r in gateway.call_log if r["kind"] == "chat.completions.stream"]
    assert any((r.get("error") or "").startswith("STREAM_INTERRUPTED") for r in records)
    # Cost reservation is not lost on interruption.
    assert gateway.spend_usd > 0.0


@pytest.mark.asyncio
async def test_missing_terminal_event_settles_once_without_zeroing(monkeypatch):
    async def upstream():
        yield _chunk(usage=None)
        # no usage-bearing terminal chunk at all

    gateway, _ = _gateway(monkeypatch, upstream)
    stream = await gateway.start_chat_stream(
        messages=_messages(),
        model="stepfun/step-3.7-flash",
        route=_route(),
    )
    [chunk async for chunk in stream.chunks]

    assert gateway.budget_status()["active_reservations"] == 0
    records = [r for r in gateway.call_log if r["kind"] == "chat.completions.stream"]
    assert len(records) == 1, "settlement must happen exactly once"
    assert gateway.spend_usd > 0.0


@pytest.mark.asyncio
async def test_stream_failure_before_first_chunk_releases_reservation(monkeypatch):
    class Completions:
        async def create(self, **kwargs):
            raise RuntimeError("upstream refused")

    gateway = LLMGateway()
    gateway.set_key("nk-test", unlock_live=True)
    gateway.cache = None
    monkeypatch.setattr(
        gateway,
        "_client_for_route",
        lambda route: SimpleNamespace(
            chat=SimpleNamespace(completions=Completions()),
        ),
    )
    with pytest.raises(RuntimeError, match="upstream refused"):
        await gateway.start_chat_stream(
            messages=_messages(),
            model="stepfun/step-3.7-flash",
            route=_route(),
        )
    assert gateway.budget_status()["active_reservations"] == 0
