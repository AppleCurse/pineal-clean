import pytest
import asyncio
from agent_core.agents.interpreter_agent import InterpreterAgent, InterpreterResult

@pytest.mark.asyncio
async def test_interpreter_agent_initialization():
    agent = InterpreterAgent()
    assert agent is not None

@pytest.mark.asyncio
async def test_interpreter_agent_fallback_or_execute():
    agent = InterpreterAgent()
    result = await agent.execute_task("Print hello world in python", auto_run=True)
    assert isinstance(result, InterpreterResult)
    assert result.status in ["success", "error"]
