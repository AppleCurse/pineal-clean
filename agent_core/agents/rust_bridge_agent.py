#!/usr/bin/env python3
"""Rust bridge for the real PinealExecutor pipeline."""

import asyncio
import json
import os
import sys
from typing import Dict, Any

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agent_core.task_executor import PinealExecutor  # noqa: E402


class RustBridgeAgent:
    def __init__(self, llm_gateway=None):
        self.llm_gateway = llm_gateway

    async def execute(self, input_data: Dict[str, Any], memory=None, llm_gateway=None) -> Dict[str, Any]:
        target_url = input_data.get("target_url", "")
        scraped_data = input_data.get("target_profile", {})
        user_freq = input_data.get("user_context", {})
        return run_full_pipeline(target_url, scraped_data, user_freq)


def _user_profile(user_freq: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "private_rituals": user_freq.get("rituals", []),
        "late_night_playlist": user_freq.get("playlist", []),
        "secret_envies": user_freq.get("envies", []),
    }


def _find_agent_result(task_status, agent_name: str) -> Dict[str, Any]:
    for entry in task_status.evidence_chain:
        if entry.get("agent") == agent_name:
            return entry.get("result", {})
    return {}


def run_full_pipeline(target_url: str, scraped_data: Dict[str, Any], user_freq: Dict[str, Any]) -> Dict[str, Any]:
    print(f"[RUST_BRIDGE] Pipeline başlatılıyor: {target_url}", file=sys.stderr)
    executor = PinealExecutor()
    user_profile = _user_profile(user_freq)
    input_data = {
        "target_url": target_url,
        "target_profile": scraped_data,
        "user_profile": user_profile,
    }

    print("[RUST_BRIDGE] PinealExecutor gerçek pipeline çalıştırılıyor...", file=sys.stderr)
    task_status = asyncio.run(executor.execute_task(input_data, "rust_bridge_task"))

    verification_result = _find_agent_result(task_status, "autonomous_verifier")
    if not verification_result:
        verification_result = {
            "verifications": [],
            "overall_authenticity_score": 0.0,
            "status": "UNVERIFIED",
        }

    print(f"[RUST_BRIDGE] Verification status: {verification_result.get('status', 'UNKNOWN')}", file=sys.stderr)

    mirror_result = _find_agent_result(task_status, "mirror_truth")
    if not mirror_result:
        mirror_result = {
            "user_core_frequency": "unknown",
            "surface_persona": "unknown",
            "authentic_anchors": [],
            "alignment_score": 0.0,
        }

    final_status = task_status.status
    verification_score = float(verification_result.get("overall_authenticity_score", 0.0))
    alignment_score = float(mirror_result.get("alignment_score", 0.0))

    return {
        "target_url": target_url,
        "verification": verification_result,
        "mirror_analysis": mirror_result,
        "alignment_score": alignment_score,
        "overall_authenticity_score": verification_score,
        "combined_score": alignment_score * 0.4 + verification_score * 0.6,
        "status": final_status,
    }


def main() -> None:
    """CLI: JSON payload is accepted on stdin; no user value is interpolated into Python source."""
    if len(sys.argv) == 2 and sys.argv[1] == "--stdin":
        try:
            payload = json.load(sys.stdin)
            result = run_full_pipeline(
                payload.get("target_url", ""),
                payload.get("target_profile", {}),
                payload.get("user_context", {}),
            )
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0 if result.get("status") in {"completed", "halted_frequency", "halted_evidence"} else 1)
        except Exception as e:
            print(json.dumps({"status": "failed", "error": str(e)}, ensure_ascii=False))
            sys.exit(1)

    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: rust_bridge_agent.py --stdin", "status": "failed"}))
        sys.exit(1)

    try:
        result = run_full_pipeline(sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3]))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("status") in {"completed", "halted_frequency", "halted_evidence"} else 1)
    except Exception as e:
        print(json.dumps({"error": f"Pipeline failed: {e}", "status": "failed"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
