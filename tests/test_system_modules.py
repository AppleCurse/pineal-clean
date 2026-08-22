import pytest
import asyncio
from agent_core.psychology.dark_triad import DarkTriadAnalyzer, DarkTriadProfile
from agent_core.shadow.shadow_executor import ShadowExecutor
from agent_core.chat.dialogue_manager import DialogueManager
from agent_core.aspasia.zeigarnik_engine import ZeigarnikEngine
from agent_core.agents.rust_bridge_agent import RustBridgeAgent

def test_dark_triad_analyzer():
    analyzer = DarkTriadAnalyzer()
    profile = {"posts": ["Her şeyi ben yönetirim", "Kimseye güvenme"], "bio": "Lider"}
    res = analyzer.analyze(profile)
    assert isinstance(res, DarkTriadProfile)
    assert 0.0 <= res.machiavellianism <= 1.0

def test_zeigarnik_engine():
    engine = ZeigarnikEngine()
    msg = engine.inject_open_loop("Merhaba", intensity=1.0)
    assert isinstance(msg, str)
    assert len(msg) >= len("Merhaba")

@pytest.mark.asyncio
async def test_dialogue_manager():
    dm = DialogueManager()
    dm.start_session("task_test", {"bio": "test"}, {"private_rituals": ["çay"]})
    assert "task_test" in dm.sessions

@pytest.mark.asyncio
async def test_rust_bridge_agent():
    agent = RustBridgeAgent()
    assert agent is not None
