import json
import pytest

from agent_core.services.llm_gateway import LLMGateway


@pytest.fixture
def gateway():
    gw = LLMGateway.__new__(LLMGateway)
    gw._rtk_policy_cache = None
    return gw


def test_policy_loads_and_caches(gateway, tmp_path, monkeypatch):
    fake_policy = {
        "enabled": True,
        "default_level": "standard",
        "bypass": {"tasks": ["depth"], "agents": ["depth_analyst"]},
    }
    fake_path = tmp_path / "rtk_policy.json"
    fake_path.write_text(json.dumps(fake_policy), encoding="utf-8")
    monkeypatch.setattr("agent_core.services.llm_gateway._RTK_POLICY_PATH", fake_path)

    result = gateway._get_rtk_policy()
    assert result["enabled"] is True
    assert "depth" in result["bypass"]["tasks"]

    # Second call should return cached policy without re-reading disk
    fake_path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    cached_result = gateway._get_rtk_policy()
    assert cached_result["enabled"] is True


def test_missing_policy_file_fails_open(gateway, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agent_core.services.llm_gateway._RTK_POLICY_PATH", tmp_path / "nonexistent.json"
    )
    result = gateway._get_rtk_policy()
    assert result["enabled"] is False


def test_should_bypass_when_disabled(gateway):
    gateway._rtk_policy_cache = {
        "enabled": False,
        "default_level": "conservative",
        "bypass": {"tasks": [], "agents": []},
    }
    assert gateway.should_bypass_rtk(task="fast_classify", agent_name="pattern_interrupt") is True


def test_should_bypass_depth_task(gateway):
    gateway._rtk_policy_cache = {
        "enabled": True,
        "default_level": "standard",
        "bypass": {"tasks": ["depth"], "agents": []},
    }
    assert gateway.should_bypass_rtk(task="depth", agent_name="anything") is True
    assert gateway.should_bypass_rtk(task="fast_classify", agent_name="anything") is False


def test_apply_rtk_compression_respects_bypass(gateway):
    gateway._rtk_policy_cache = {
        "enabled": True,
        "default_level": "standard",
        "bypass": {"tasks": [], "agents": ["depth_analyst"]},
    }
    original = "hello    world"
    result = gateway._apply_rtk_compression(original, task="depth", agent_name="depth_analyst")
    assert result == original


def test_apply_rtk_compression_never_raises_on_internal_error(gateway):
    gateway._rtk_policy_cache = {
        "enabled": True,
        "default_level": "INVALID_LEVEL",
        "bypass": {"tasks": [], "agents": []},
    }
    result = gateway._apply_rtk_compression("test", task=None, agent_name=None)
    assert result == "test"


def test_compress_chat_messages_skips_image_url_parts(gateway):
    gateway._rtk_policy_cache = {
        "enabled": True,
        "default_level": "conservative",
        "bypass": {"tasks": [], "agents": []},
    }
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello    world"},
                {"type": "image_url", "image_url": {"url": "http://example.com/x.jpg"}},
            ],
        }
    ]
    result = gateway._compress_chat_messages(messages, task=None, agent_name=None)
    assert result[0]["content"][0]["text"] == "hello world"
    assert result[0]["content"][1] == {"type": "image_url", "image_url": {"url": "http://example.com/x.jpg"}}


def test_compress_chat_messages_string_content(gateway):
    gateway._rtk_policy_cache = {
        "enabled": True,
        "default_level": "conservative",
        "bypass": {"tasks": [], "agents": []},
    }
    messages = [{"role": "user", "content": "a    b"}]
    result = gateway._compress_chat_messages(messages, task=None, agent_name=None)
    assert result[0]["content"] == "a b"


def test_env_override_extends_not_replaces_bypass_list(gateway, tmp_path, monkeypatch):
    fake_policy = {
        "enabled": True,
        "default_level": "standard",
        "bypass": {"tasks": ["depth"], "agents": []},
    }
    fake_path = tmp_path / "rtk_policy.json"
    fake_path.write_text(json.dumps(fake_policy), encoding="utf-8")
    monkeypatch.setattr("agent_core.services.llm_gateway._RTK_POLICY_PATH", fake_path)
    monkeypatch.setenv("PINEAL_RTK_BYPASS_TASKS", "extra_task")

    result = gateway._get_rtk_policy()
    assert "depth" in result["bypass"]["tasks"]
    assert "extra_task" in result["bypass"]["tasks"]


def test_disk_rtk_policy_contract_locks_all_bypass_agents_and_tasks():
    """Diskteki rtk_policy.json dosyasının tüm bypass ajanlarını ve görevlerini kilitler."""
    gw = LLMGateway()
    assert gw.should_bypass_rtk(agent_name="human_behavior") is True
    assert gw.should_bypass_rtk(agent_name="shadow_executor") is True
    assert gw.should_bypass_rtk(agent_name="lilith_growth") is True
    assert gw.should_bypass_rtk(agent_name="depth_analyst") is True
    assert gw.should_bypass_rtk(agent_name="mirror_truth") is True
    assert gw.should_bypass_rtk(agent_name="authenticity_auditor") is True
    assert gw.should_bypass_rtk(task="depth") is True
    assert gw.should_bypass_rtk(task="reasoning") is True

    # Çift yönlü kilit: Sadece bypass listesindekilerin True olduğunu değil,
    # non-bypass ajan/görevlerin False döndüğünü de doğrular (enabled=true doğrulaması).
    assert gw.should_bypass_rtk(agent_name="dialogue_manager") is False
    assert gw.should_bypass_rtk(task="vision") is False

