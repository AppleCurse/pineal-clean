"""
P0.2 — AutonomousVerifier: Yetersiz kanıt varsa 1.0 yasak.
KIZIL TEST: tavily_key yoksa score == 0.0, status == "UNVERIFIED" olmalı.
"""
import pytest
from unittest.mock import MagicMock
from agent_core.agents.autonomous_verifier import AutonomousVerifier


@pytest.mark.asyncio
async def test_no_tavily_key_returns_unverified():
    """search_engine.tavily_key = None → score 0.0, status UNVERIFIED."""
    mock_search = MagicMock()
    mock_search.tavily_key = None  # API key yok

    verifier = AutonomousVerifier(search_engine=mock_search)
    report = await verifier.execute(
        {"target_profile": {"bio": "Türkiye'nin en büyük girişimcisi"}},
        memory=None,
        llm_gateway=None,
    )

    assert report.status == "UNVERIFIED", f"Beklenen UNVERIFIED, gelen: {report.status}"
    assert report.overall_authenticity_score == 0.0, (
        f"Beklenen 0.0, gelen: {report.overall_authenticity_score}"
    )


@pytest.mark.asyncio
async def test_empty_bio_returns_unverified():
    """bio = '' → score 0.0, status UNVERIFIED."""
    mock_search = MagicMock()
    mock_search.tavily_key = "some-key"

    verifier = AutonomousVerifier(search_engine=mock_search)
    report = await verifier.execute(
        {"target_profile": {"bio": ""}},
        memory=None,
        llm_gateway=None,
    )

    assert report.status == "UNVERIFIED", f"Beklenen UNVERIFIED, gelen: {report.status}"
    assert report.overall_authenticity_score == 0.0, (
        f"Beklenen 0.0, gelen: {report.overall_authenticity_score}"
    )


@pytest.mark.asyncio
async def test_no_target_profile_returns_unverified():
    """target_profile eksik → score 0.0, status UNVERIFIED."""
    mock_search = MagicMock()
    mock_search.tavily_key = None

    verifier = AutonomousVerifier(search_engine=mock_search)
    report = await verifier.execute(
        {"target_profile": {}},
        memory=None,
        llm_gateway=None,
    )

    assert report.status == "UNVERIFIED", f"Beklenen UNVERIFIED, gelen: {report.status}"
    assert report.overall_authenticity_score == 0.0, (
        f"Beklenen 0.0, gelen: {report.overall_authenticity_score}"
    )


@pytest.mark.asyncio
async def test_score_never_1_without_evidence():
    """Hiçbir arama yapılmadan score == 1.0 olamaz (P0.2 sahte başarı yasağı)."""
    mock_search = MagicMock()
    mock_search.tavily_key = ""  # boş string — falsy

    verifier = AutonomousVerifier(search_engine=mock_search)
    report = await verifier.execute(
        {"target_profile": {"bio": "En iyi doktor"}},
        memory=None,
        llm_gateway=None,
    )

    assert report.overall_authenticity_score != 1.0, (
        "HATA: Kanıt olmadan score 1.0 döndürüldü — P0.2 ihlali!"
    )
