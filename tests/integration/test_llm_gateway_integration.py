import pytest
import os
import asyncio
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_llm_gateway_no_flag_raises_error(monkeypatch):
    monkeypatch.delenv("LIVE_LLM_E2E", raising=False)
    monkeypatch.setenv("USE_LOCAL_LLM", "false")
    gateway = LLMGateway()
    
    with pytest.raises(RuntimeError) as exc:
        await gateway.query("Test", tier=1, model="gpt-4")
        
    assert "REAL_LLM_CALL_NOT_EXECUTED" in str(exc.value)

class MockAsyncCompletions:
    def __init__(self, fails=0, exception_msg="rate limit 429"):
        self.fails = fails
        self.attempts = 0
        self.exception_msg = exception_msg

    async def create(self, **kwargs):
        self.attempts += 1
        if self.attempts <= self.fails:
            raise Exception(self.exception_msg)
            
        class MockChoice:
            class MockMsg:
                content = "success"
            message = MockMsg()
            
        class MockResponse:
            choices = [MockChoice()]
            
        return MockResponse()

class MockClient:
    def __init__(self, fails=0, exception_msg="rate limit 429"):
        self.chat = type('MockChat', (), {'completions': MockAsyncCompletions(fails, exception_msg)})()

@pytest.mark.asyncio
async def test_llm_gateway_rate_limit_retry(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    monkeypatch.setenv("USE_LOCAL_LLM", "false")
    gateway = LLMGateway()
    gateway.client = MockClient(fails=2, exception_msg="429 Too Many Requests")
    
    res = await gateway.query("Test", tier=1, model="gpt-4")
    assert res == "success"
    assert gateway.client.chat.completions.attempts == 3

@pytest.mark.asyncio
async def test_llm_gateway_auth_error(monkeypatch):
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    monkeypatch.setenv("USE_LOCAL_LLM", "false")
    gateway = LLMGateway()
    gateway.client = MockClient(fails=1, exception_msg="401 Unauthorized")
    
    with pytest.raises(RuntimeError) as exc:
        await gateway.query("Test", tier=1, model="gpt-4")
        
    assert "LLM API Key rejected" in str(exc.value)
    assert gateway.client.chat.completions.attempts == 1
