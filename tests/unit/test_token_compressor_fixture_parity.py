"""
Rust ve Python token_compressor implementasyonlarının ORTAK
fixture dosyasından (rust_core/tests/fixtures/compression_cases.json)
aynı sonuçları ürettiğini doğrular. Sapma = kırmızı test.
"""
import json
from pathlib import Path

import pytest

from agent_core.services.token_compressor import compress_prompt, CompressionLevel

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent
    / "rust_core" / "tests" / "fixtures" / "compression_cases.json"
)


def _load_cases():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_fixture_case(case):
    output = compress_prompt(case["input"], CompressionLevel(case["level"]))

    if "expected" in case:
        assert output == case["expected"], f"[{case['id']}] mismatch"

    if "expected_contains" in case:
        assert case["expected_contains"] in output, f"[{case['id']}] missing substring"

    if "expected_trimmed" in case:
        assert output.strip() == case["expected_trimmed"], f"[{case['id']}] trimmed mismatch"

    if "expected_line_count" in case:
        for needle, expected_count in case["expected_line_count"].items():
            actual = sum(1 for line in output.split("\n") if line.strip() == needle.strip())
            assert actual == expected_count, (
                f"[{case['id']}] line_count({needle!r}) expected={expected_count} got={actual}"
            )


def test_fixture_file_exists_and_not_empty():
    assert FIXTURE_PATH.exists(), "Ortak fixture dosyası bulunamadı"
    cases = _load_cases()
    assert len(cases) > 0


def test_compress_prompt_never_raises_on_arbitrary_input():
    """Fail-open garantisi: hiçbir girdi exception fırlatmamalı."""
    weird_inputs = ["", "   ", "\0", "\ufeff test", "𝔘𝔫𝔦𝔠𝔬𝔡𝔢", None]
    for inp in weird_inputs:
        try:
            result = compress_prompt(inp, CompressionLevel.STANDARD)  # type: ignore
            assert isinstance(result, str) or inp is None
        except Exception as e:
            pytest.fail(f"compress_prompt exception fırlattı: {inp!r} -> {e}")