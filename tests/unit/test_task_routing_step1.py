"""Step 1 task-routing locks (config + resolver + gateway precedence).

Scope (locked): config/task_routing.json (5 agents, registry keys only),
pure resolver (agent_name, task) -> keys | None, gateway precedence
env-override > task_routing > AGENT_CHAINS > task fallback with
chain_source="task_routing" telemetry.

Mutation doctrine applies: each guarded check below must go red when its
guard is broken (proven per session, not per commit).
"""

import ast
import json
import sys
from pathlib import Path

import pytest

import agent_core.services.llm_gateway as gwl
from agent_core.services import task_routing_resolver as trr
from agent_core.services.llm_gateway import LLMGateway

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_SRC = Path(trr.__file__).read_text(encoding="utf-8")
SHIPPED_CONFIG = REPO_ROOT / "config" / "task_routing.json"

VALID = frozenset(LLMGateway.MODEL_REGISTRY.keys())

ROUTED_AGENTS = [
    "depth_analyst",
    "human_behavior",
    "dialogue_manager",
    "shadow_executor",
    "interpreter",
]


@pytest.fixture(autouse=True)
def _hermetic_routing_env(monkeypatch):
    monkeypatch.delenv("PINEAL_TASK_ROUTING_PATH", raising=False)
    for agent in ROUTED_AGENTS + ["friction_detector"]:
        monkeypatch.delenv(f"OPENROUTER_AGENT_CHAIN_{agent.upper()}", raising=False)
    yield


def _write_routing(tmp_path, table):
    path = tmp_path / "task_routing.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    return path


def _source_of(gw, agent_name, task):
    gw.get_agent_chain(agent_name, task)
    return gwl._active_chain_source.get()


# ------------------------------------------------ 1) import-graph purity
def test_resolver_import_graph_is_stdlib_only():
    """Resolver may import stdlib only: no health/governor/registry/agent_core."""
    tree = ast.parse(RESOLVER_SRC)
    allowed = set(sys.stdlib_module_names) | {"__future__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in allowed, f"non-stdlib import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import forbidden in resolver"
            root = (node.module or "").split(".")[0]
            assert root in allowed, f"non-stdlib import: {node.module}"
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else ""
            assert name not in {"__import__", "eval", "exec"}, "dynamic import forbidden"


# ------------------------------------------------ 2) resolver unit behavior
def test_resolver_returns_validated_keys_and_ignores_task(tmp_path):
    path = _write_routing(
        tmp_path,
        {"depth_analyst": ["deepseek_v4_pro", "claude_sonnet_5", "gemini_3_7_flash"]},
    )
    expected = ["deepseek_v4_pro", "claude_sonnet_5", "gemini_3_7_flash"]
    for task in ("depth", "vision", "dialogue", None):
        assert trr.resolve_task_chain("depth_analyst", task, valid_keys=VALID, explicit_path=path) == expected


def test_resolver_fail_closed_matrix(tmp_path):
    path = _write_routing(
        tmp_path,
        {
            "_meta": {"purpose": "meta must never resolve"},
            "good": ["claude_sonnet_5", "gemini_3_7_flash"],
            "bad_key": ["claude_sonnet_5", "nope_not_a_key"],
            "value_not_key": ["anthropic/claude-sonnet-5"],
            "empty": [],
            "not_a_list": "claude_sonnet_5",
            "non_str": ["claude_sonnet_5", 7],
        },
    )
    kw = {"valid_keys": VALID, "explicit_path": path}
    assert trr.resolve_task_chain("good", "depth", **kw) == ["claude_sonnet_5", "gemini_3_7_flash"]
    # Unknown / miscased / meta / mistyped agent -> None (falls through).
    assert trr.resolve_task_chain("yok-boyle-ajan", "depth", **kw) is None
    assert trr.resolve_task_chain("Depth_Analyst", "depth", **kw) is None
    assert trr.resolve_task_chain("_meta", "depth", **kw) is None
    assert trr.resolve_task_chain("", "depth", **kw) is None
    assert trr.resolve_task_chain(None, "depth", **kw) is None
    assert trr.resolve_task_chain(123, "depth", **kw) is None
    # Any invalid id poisons the WHOLE entry: no partial amputation.
    assert trr.resolve_task_chain("bad_key", "depth", **kw) is None
    assert trr.resolve_task_chain("value_not_key", "depth", **kw) is None
    assert trr.resolve_task_chain("empty", "depth", **kw) is None
    assert trr.resolve_task_chain("not_a_list", "depth", **kw) is None
    assert trr.resolve_task_chain("non_str", "depth", **kw) is None
    # No validation authority -> fail closed.
    assert trr.resolve_task_chain("good", "depth", explicit_path=path) is None
    # Missing / corrupt file -> None (gateway falls through to matrix).
    assert trr.resolve_task_chain("good", "depth", valid_keys=VALID, explicit_path=tmp_path / "yok.json") is None
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{gecersiz", encoding="utf-8")
    assert trr.resolve_task_chain("good", "depth", valid_keys=VALID, explicit_path=corrupt) is None


def test_resolver_default_path_follows_parents2_convention():
    assert trr.TASK_ROUTING_PATH == REPO_ROOT / "config" / "task_routing.json"
    assert trr.TASK_ROUTING_PATH_ENV == "PINEAL_TASK_ROUTING_PATH"


# ------------------------------------------------ 3) gateway precedence (fixture routing)
def test_gateway_precedence_env_over_task_routing_over_matrix(tmp_path, monkeypatch):
    path = _write_routing(tmp_path, {"friction_detector": ["grok_4_6"]})
    monkeypatch.setenv("PINEAL_TASK_ROUTING_PATH", str(path))
    gw = LLMGateway()

    monkeypatch.setenv("OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR", "custom/a, custom/b")
    assert gw.get_agent_chain("friction_detector", "depth") == ["custom/a", "custom/b"]
    assert gwl._active_chain_source.get() == "env_override"

    monkeypatch.delenv("OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR")
    assert gw.get_agent_chain("friction_detector", "depth") == ["x-ai/grok-4.6"]
    assert gwl._active_chain_source.get() == "task_routing"


def test_gateway_matrix_and_task_fallback_untouched(tmp_path, monkeypatch):
    path = _write_routing(tmp_path, {"someone_else": ["grok_4_6"]})
    monkeypatch.setenv("PINEAL_TASK_ROUTING_PATH", str(path))
    gw = LLMGateway()

    assert gw.get_agent_chain("friction_detector", "depth") == [
        "anthropic/claude-sonnet-5",
        "deepseek/deepseek-v4-pro",
    ]
    assert gwl._active_chain_source.get() == "agent_matrix"

    assert gw.get_agent_chain("yok-boyle-ajan", "depth") == gw.get_chain("depth")
    assert gwl._active_chain_source.get() == "task_chain"
    assert gw.get_agent_chain(None, "vision") == gw.get_chain("vision")
    assert gwl._active_chain_source.get() == "task_chain"


# ------------------------------------------------ 4) shipped config: exact flips + new chains
def test_shipped_config_exact_flips():
    gw = LLMGateway()
    assert gw.get_agent_chain("depth_analyst", "depth") == [
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    assert gwl._active_chain_source.get() == "task_routing"
    assert gw.get_agent_chain("human_behavior", "depth") == [
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    assert gwl._active_chain_source.get() == "task_routing"


def test_shipped_config_new_explicit_chains():
    gw = LLMGateway()
    assert gw.get_agent_chain("dialogue_manager", "dialogue") == [
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    assert gwl._active_chain_source.get() == "task_routing"
    assert gw.get_agent_chain("shadow_executor", "depth") == [
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    assert gwl._active_chain_source.get() == "task_routing"
    assert gw.get_agent_chain("interpreter", "fast") == [
        "anthropic/claude-sonnet-5",
        "deepseek/deepseek-v4-flash",
    ]
    assert gwl._active_chain_source.get() == "task_routing"


def test_shipped_config_contract():
    data = json.loads(SHIPPED_CONFIG.read_text(encoding="utf-8"))
    agents = {k: v for k, v in data.items() if not k.startswith("_") and k != "schema_version"}
    assert trr.resolve_task_chain("schema_version", "depth", valid_keys=VALID) is None
    assert sorted(agents) == sorted(ROUTED_AGENTS)
    registry = set(LLMGateway.MODEL_REGISTRY.keys())
    for agent, chain in agents.items():
        assert isinstance(chain, list) and len(chain) >= 2, agent
        assert set(chain) <= registry, agent
    assert data["schema_version"] == 1
    assert "task_routing" in data["_meta"]["precedence"]


def test_casing_rejection_falls_through_to_task_chain():
    gw = LLMGateway()
    assert gw.get_agent_chain("Depth_Analyst", "depth") == gw.get_chain("depth")
    assert gwl._active_chain_source.get() == "task_chain"


# ------------------------------------------------ 5) capable_chain interaction
def test_capable_chain_vision_interaction_with_routed_chains():
    gw = LLMGateway()
    # human_behavior: both routed models vision-eligible -> chain intact.
    assert gw.capable_chain(task="depth", agent_name="human_behavior", images=["http://x/i.png"]) == [
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    # depth_analyst: deepseek_v4_pro is NOT vision-eligible -> filtered when images present.
    assert gw.capable_chain(task="depth", agent_name="depth_analyst", images=["http://x/i.png"]) == [
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    # ...but kept when no vision is required.
    assert gw.capable_chain(task="depth", agent_name="depth_analyst") == [
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
