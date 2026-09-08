"""
task_routing_resolver.py — Step 1 task routing resolver (PURE).

Maps (agent_name, task) -> validated MODEL_REGISTRY key list, or None.

Purity contract (locked by tests, mirror of test_rust_runtime_status.py style):
- stdlib ONLY (json/os/pathlib/typing). No agent_core imports, no health,
  no governor, no registry imports. The validation authority (valid_keys)
  is INJECTED by the caller (the gateway passes frozenset(MODEL_REGISTRY)).
- No caching, no I/O beyond a single config read per call. The file is tiny
  and OS page-cached; correctness (fresh reads, hermetic tests) beats µs.
- Fail-closed: unknown agent -> None; any invalid key in an entry -> None
  for that entry (NO partial amputation); missing/corrupt file -> None.

Config path follows the provider_manager.py convention:
    Path(__file__).resolve().parents[2] / "config" / "task_routing.json"
Tests/ops may override with the PINEAL_TASK_ROUTING_PATH env var.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

TASK_ROUTING_PATH = Path(__file__).resolve().parents[2] / "config" / "task_routing.json"
TASK_ROUTING_PATH_ENV = "PINEAL_TASK_ROUTING_PATH"


def _config_path(explicit: Optional[str | Path] = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    override = os.getenv(TASK_ROUTING_PATH_ENV, "").strip()
    if override:
        return Path(override)
    return TASK_ROUTING_PATH


def load_task_routing(explicit_path: Optional[str | Path] = None) -> dict:
    """Load the raw routing table. Returns {} on any failure (fail-closed)."""
    try:
        with open(_config_path(explicit_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_task_chain(
    agent_name: str | None,
    task: object = None,
    *,
    valid_keys: frozenset[str] | set[str] | None = None,
    explicit_path: Optional[str | Path] = None,
) -> list[str] | None:
    """Resolve (agent_name, task) -> ordered registry KEYS, or None.

    - agent_name: exact snake_case match only. No case folding: "Depth_Analyst"
      resolves to None. "_" prefixed names resolve to None (meta guard).
    - task: RESERVED for future task-level chains; accepted and ignored in v1.
    - valid_keys: injected validation authority (gateway passes the registry
      key set). None -> fail-closed None (cannot validate without authority).
    - Returns KEYS (e.g. "claude_sonnet_5"), never model-id values. The gateway
      maps keys -> MODEL_REGISTRY values.
    """
    _ = task  # reserved (v1: agent-keyed only)
    if not isinstance(agent_name, str) or not agent_name:
        return None
    if agent_name.startswith("_"):
        return None
    if valid_keys is None:
        return None

    data = load_task_routing(explicit_path)
    entry = data.get(agent_name)
    if not isinstance(entry, list) or not entry:
        return None
    for key in entry:
        if not isinstance(key, str) or key not in valid_keys:
            return None  # fail-closed: no partial amputation
    return list(entry)
