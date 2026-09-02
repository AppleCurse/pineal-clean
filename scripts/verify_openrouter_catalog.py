#!/usr/bin/env python3
"""CI verifier for the OpenRouter facts Pineal depends on.

Two independent, deliberately separated checks:

1. **Local catalog contract** (always runs, no network): the pinned
   ``config/provider_catalog.json`` must contain the paid OpenRouter models
   Pineal uses, with the exact FINAL-KARAR-MATRIX prices. This also guards the
   free/paid boundary: a ``:free``-suffixed model must really be priced $0, and
   no model is ever classified free just because OpenRouter lists it.

2. **Live OpenRouter check** (only when ``OPENROUTER_API_KEY`` is set): fetch
   ``/api/v1/models`` and cross-check that the required paid models exist with
   the expected prices. A missing model or a price drift fails the run.

OpenRouter presence/absence is NEVER treated as evidence about the Nous
catalog. Nous facts are owned by the FINAL routing policy and the local
catalog, which this script also verifies separately.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "config" / "provider_catalog.json"

# OpenRouter models Pineal must be able to route through with exact prices
# ($ per 1M tokens, input/output). Verified against the decision matrix.
REQUIRED_OPENROUTTER = {
    "google/gemini-3.7-flash": (0.75, 3.75),
    "openai/gpt-5.6-sol-pro": (2.0, 10.0),
}

# Nous FINAL-KARAR-MATRIX facts. These are verified locally, never against
# the OpenRouter catalog.
REQUIRED_NOUS_FREE = {
    "laguna-s-2.1:free",
    "xs-2.1:free",
    "ling-3.0-flash-fin:free",
    "dots-3-note-preview:free",
}
REQUIRED_NOUS_PAID = {
    "stepfun/step-3.7-flash": (0.20, 1.15),
    "upstage/solar-pro4": (0.03, 0.12),
    "meituan/longcat-2.0": (0.30, 1.20),
    "openai/gpt-5.6-luna": (0.20, 1.20),
    "anthropic/claude-sonnet-5": (1.60, 8.00),
}


def _load_catalog() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _catalog_models(catalog: dict) -> dict[str, dict]:
    models: dict[str, dict] = {}
    for provider in catalog.get("providers", []):
        provider_id = provider.get("id", "")
        for model in provider.get("models", []):
            models[f"{provider_id}/{model.get('id', '')}"] = model
    return models


def _pricing(model: dict) -> tuple[float, float]:
    pricing = model.get("pricing") or {}
    return (
        float(pricing.get("input_per_million_usd", 0.0)),
        float(pricing.get("output_per_million_usd", 0.0)),
    )


def verify_local_catalog() -> list[str]:
    """Deterministic local contract checks. Returns a list of failures."""
    failures: list[str] = []
    catalog = _load_catalog()
    if catalog.get("schema_version") != 1:
        failures.append("catalog schema_version must be 1")
        return failures
    models = _catalog_models(catalog)

    for model_id, (expected_in, expected_out) in REQUIRED_OPENROUTTER.items():
        model = models.get(f"openrouter/{model_id}")
        if model is None:
            failures.append(f"openrouter/{model_id}: missing from local catalog")
            continue
        actual_in, actual_out = _pricing(model)
        if abs(actual_in - expected_in) > 1e-9 or abs(actual_out - expected_out) > 1e-9:
            failures.append(
                f"openrouter/{model_id}: price drift "
                f"({actual_in}/{actual_out}) != ({expected_in}/{expected_out})"
            )

    nous_present = any(
        provider.get("id") == "nous-research" for provider in catalog.get("providers", [])
    )
    if not nous_present:
        failures.append("nous-research: provider missing from local catalog")
    else:
        for free_id in REQUIRED_NOUS_FREE:
            model = models.get(f"nous-research/{free_id}")
            if model is None:
                failures.append(f"nous-research/{free_id}: missing free route")
                continue
            actual_in, actual_out = _pricing(model)
            if actual_in != 0.0 or actual_out != 0.0:
                failures.append(f"nous-research/{free_id}: free route is not priced $0")
        for paid_id, (expected_in, expected_out) in REQUIRED_NOUS_PAID.items():
            model = models.get(f"nous-research/{paid_id}")
            if model is None:
                failures.append(f"nous-research/{paid_id}: missing paid route")
                continue
            actual_in, actual_out = _pricing(model)
            if abs(actual_in - expected_in) > 1e-9 or abs(actual_out - expected_out) > 1e-9:
                failures.append(
                    f"nous-research/{paid_id}: price drift "
                    f"({actual_in}/{actual_out}) != ({expected_in}/{expected_out})"
                )

    # Free/paid boundary: a ':free' suffix must be genuinely priced $0 and must
    # not be a retired/incorrect alias in the catalog.
    for canonical, model in models.items():
        if ":free" in canonical:
            actual_in, actual_out = _pricing(model)
            if actual_in != 0.0 or actual_out != 0.0:
                failures.append(f"{canonical}: ':free' suffix but priced > $0")

    # Spec section 13: gemma-3-27b-it:free must NOT be a verified route even if
    # it exists in the general OpenRouter catalog.
    if "nous-research/google/gemma-3-27b-it:free" in models:
        failures.append("nous-research/google/gemma-3-27b-it:free must not be catalogued")
    return failures


def verify_live_openrouter(key: str) -> list[str]:
    """Cross-check the live OpenRouter catalog. Returns a list of failures."""
    failures: list[str] = []
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    models = {item.get("id"): item for item in payload.get("data", [])}
    for model_id, (expected_in, expected_out) in REQUIRED_OPENROUTTER.items():
        item = models.get(model_id)
        if not item:
            failures.append(f"{model_id}: missing from live OpenRouter catalog")
            continue
        pricing = item.get("pricing", {})
        actual_in = float(pricing.get("prompt", 0))
        actual_out = float(pricing.get("completion", 0))
        if abs(actual_in - expected_in / 1_000_000) > 1e-12:
            failures.append(f"{model_id}: live input price {actual_in} != {expected_in}/1M")
        if abs(actual_out - expected_out / 1_000_000) > 1e-12:
            failures.append(f"{model_id}: live output price {actual_out} != {expected_out}/1M")
    return failures


def main() -> int:
    failures = verify_local_catalog()

    key = None
    try:
        import os

        key = os.getenv("OPENROUTER_API_KEY")
    except Exception:  # pragma: no cover - import cannot realistically fail
        key = None

    if not key:
        print("SKIP: live OpenRouter check (OPENROUTER_API_KEY not configured)")
    else:
        try:
            failures.extend(verify_live_openrouter(key))
        except Exception as exc:  # network/parse failures fail the gate
            failures.append(f"live OpenRouter check failed: {type(exc).__name__}: {exc}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: local catalog contract verified" + (
        " + live OpenRouter models verified" if key else ""
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
