import pytest

from agent_core.engines.alf_engine import ALF_Engine, FetchUnavailable


@pytest.mark.asyncio
async def test_alf_fetch_stops_after_bounded_attempts(monkeypatch):
    engine = ALF_Engine()
    calls = 0

    class FailingSession:
        closed = False
        def get(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            raise __import__("aiohttp").ClientConnectionError("offline")

    async def session():
        return FailingSession()

    async def no_sleep(*_):
        return None

    monkeypatch.setattr(engine, "_get_session", session)
    monkeypatch.setattr("agent_core.engines.alf_engine.asyncio.sleep", no_sleep)

    with pytest.raises(FetchUnavailable, match="after 3 attempts"):
        await engine.stealth_fetch("https://example.test", max_attempts=3)
    assert calls == 3
