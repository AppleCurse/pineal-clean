"""
P0.3 — RustBridgeAgent:
  1. Hardcoded 0.5 fallback YOK
  2. evidence_chain → verifier score → output score zinciri
  3. Verifier yoksa score = 0.0, status = UNVERIFIED
"""
import pytest
from unittest.mock import MagicMock, patch
from agent_core.agents.rust_bridge_agent import (
    RustBridgeAgent,
    _find_agent_result,
    run_full_pipeline,
)


# ------------------------------------------------------------------
# Yardımcı: sahte task_status objesi (evidence_chain attribute'lu)
# ------------------------------------------------------------------
def _make_task_status(evidence_chain: list, status: str = "completed"):
    ts = MagicMock()
    ts.status = status
    ts.evidence_chain = evidence_chain
    return ts


# ------------------------------------------------------------------
# TEST 1: _find_agent_result — doğru agent'ı döndürür
# ------------------------------------------------------------------
def test_find_agent_result_returns_correct_entry():
    """evidence_chain içinde 'autonomous_verifier' entry'si bulunmalı."""
    ts = _make_task_status([
        {"agent": "interpreter", "result": {"x": 1}},
        {"agent": "autonomous_verifier", "result": {"overall_authenticity_score": 0.83, "status": "VERIFIED", "verifications": []}},
    ])
    result = _find_agent_result(ts, "autonomous_verifier")
    assert result["overall_authenticity_score"] == 0.83
    assert result["status"] == "VERIFIED"


# ------------------------------------------------------------------
# TEST 2: _find_agent_result — agent yoksa boş dict döner (0.5 değil)
# ------------------------------------------------------------------
def test_find_agent_result_missing_returns_empty_not_half():
    """Eksik agent için 0.5 DEĞİL boş dict dönmeli."""
    ts = _make_task_status([
        {"agent": "interpreter", "result": {"x": 1}},
    ])
    result = _find_agent_result(ts, "autonomous_verifier")
    assert result == {}
    assert result.get("overall_authenticity_score", 0.0) != 0.5


# ------------------------------------------------------------------
# TEST 3: run_full_pipeline — verifier=0.83 → output=0.83
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_propagates_verifier_score():
    """Pipeline, evidence_chain'deki verifier score'unu çıktıya doğru taşımalı."""
    evidence = [
        {
            "agent": "autonomous_verifier",
            "result": {
                "verifications": [],
                "overall_authenticity_score": 0.83,
                "status": "VERIFIED",
            },
        },
        {
            "agent": "mirror_truth",
            "result": {
                "user_core_frequency": "yüksek",
                "surface_persona": "sakin",
                "authentic_anchors": ["müzik"],
                "alignment_score": 0.7,
            },
        },
    ]
    fake_task_status = _make_task_status(evidence, status="completed")

    # asyncio.run doğrudan mock'lanıyor — AsyncMock kullanmıyoruz (GC RuntimeWarning önlenir)
    with patch("agent_core.agents.rust_bridge_agent.asyncio.run", return_value=fake_task_status), \
         patch("agent_core.agents.rust_bridge_agent.PinealExecutor"):
        result = run_full_pipeline("http://example.com", {}, {})

    assert result["overall_authenticity_score"] == 0.83, (
        f"Beklenen 0.83, gelen: {result['overall_authenticity_score']}"
    )
    assert result["overall_authenticity_score"] != 0.5, "HATA: Hardcoded 0.5 yasağı ihlal edildi!"
    assert result["status"] == "completed"


# ------------------------------------------------------------------
# TEST 4: run_full_pipeline — verifier YOK → score=0.0, UNVERIFIED
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_no_verifier_returns_zero_unverified():
    """evidence_chain'de verifier yoksa output.score=0.0, status=UNVERIFIED."""
    evidence = [
        {
            "agent": "mirror_truth",
            "result": {
                "user_core_frequency": "bilinmiyor",
                "surface_persona": "bilinmiyor",
                "authentic_anchors": [],
                "alignment_score": 0.0,
            },
        },
    ]
    fake_task_status = _make_task_status(evidence, status="completed")

    # asyncio.run doğrudan mock'lanıyor — AsyncMock yok
    with patch("agent_core.agents.rust_bridge_agent.asyncio.run", return_value=fake_task_status), \
         patch("agent_core.agents.rust_bridge_agent.PinealExecutor"):
        result = run_full_pipeline("http://example.com", {}, {})

    assert result["overall_authenticity_score"] == 0.0, (
        f"Beklenen 0.0, gelen: {result['overall_authenticity_score']}"
    )
    assert result["verification"]["status"] == "UNVERIFIED", (
        f"Beklenen UNVERIFIED, gelen: {result['verification']['status']}"
    )
    assert result["overall_authenticity_score"] != 0.5, "HATA: Hardcoded 0.5 yasağı ihlal edildi!"


# ------------------------------------------------------------------
# TEST 5: RustBridgeAgent.execute — delegator doğru input gönderir
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rust_bridge_agent_execute_delegates_correctly():
    """RustBridgeAgent.execute, run_full_pipeline'a doğru argümanları iletmeli."""
    with patch("agent_core.agents.rust_bridge_agent.run_full_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {
            "overall_authenticity_score": 0.75,
            "status": "completed",
            "verification": {"status": "VERIFIED", "overall_authenticity_score": 0.75, "verifications": []},
            "mirror_analysis": {},
            "alignment_score": 0.6,
            "combined_score": 0.69,
            "target_url": "http://test.com",
        }
        agent = RustBridgeAgent()
        result = await agent.execute({
            "target_url": "http://test.com",
            "target_profile": {"name": "Test"},
            "user_context": {"rituals": ["sabah koşusu"]},
        }, memory=None, llm_gateway=None)

    mock_pipeline.assert_called_once_with(
        "http://test.com",
        {"name": "Test"},
        {"rituals": ["sabah koşusu"]},
    )
    assert result["overall_authenticity_score"] != 0.5
    assert result["overall_authenticity_score"] == 0.75
