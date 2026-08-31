"""Canonical, machine-readable status for non-Python repository components."""

from __future__ import annotations


# Phase 9 decision B: Rust remains an independently validated experiment. It is
# deliberately not a Python dependency, is not copied into the product Docker
# image, and cannot affect API/pipeline decisions. Changing this contract to
# integrated requires a real product-path call and cross-stack effect test.
_RUST_CORE_STATUS = {
    "classification": "experimental_optional",
    "product_runtime_integrated": False,
    "product_decision_effect": False,
    "packaged_in_python_runtime": False,
    "activation_flag": None,
    "validation": "ci_cargo_check_and_test",
}


def rust_core_status() -> dict:
    """Return a copy so callers cannot mutate the process-wide contract."""
    return dict(_RUST_CORE_STATUS)
