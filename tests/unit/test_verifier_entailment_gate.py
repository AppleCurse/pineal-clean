"""Unit tests for AutonomousVerifier entailment gate and fail-closed integrity."""
from types import SimpleNamespace
import pytest

from agent_core.agents.autonomous_verifier import (
    AutonomousVerifier,
    Claim,
    VerificationResult,
    VerifierReport,
    _audit_vote,
    _canonical_vote,
)


def test_canonical_vote_vocabulary():
    assert _canonical_vote("DOĞRULANDI") == "DOĞRULANDI"
    assert _canonical_vote(" doğrulanDI ") == "DOĞRULANDI"
    assert _canonical_vote("ÇELİŞKİLİ") == "ÇELİŞKİLİ"
    assert _canonical_vote("YALAN") == "YALAN"
    assert _canonical_vote("BİLİNMİYOR") == "BİLİNMİYOR"
    # Invalid strings must fall back to BİLİNMİYOR
    assert _canonical_vote("EVET_DOGRU") == "BİLİNMİYOR"
    assert _canonical_vote("TRUE") == "BİLİNMİYOR"
    assert _canonical_vote("FAKE") == "BİLİNMİYOR"
    assert _canonical_vote("") == "BİLİNMİYOR"
    assert _canonical_vote(None) == "BİLİNMİYOR"


def test_audit_vote_hallucinated_url():
    sources = [
        SimpleNamespace(source_url="https://legit.org/profile", content="Dr. Ahmet beyin cerrahıdır.")
    ]
    # Juror hallucinated an external URL not present in sources
    v, note = _audit_vote(
        vote="DOĞRULANDI",
        evidence_url="https://fake-hallucination.xyz/bad",
        evidence_quote="",
        claim_text="Beyin cerrahı",
        sources=sources,
    )
    assert v == "BİLİNMİYOR"
    assert note and "halusinasyon_url" in note


def test_audit_vote_valid_url_and_quote():
    sources = [
        SimpleNamespace(source_url="https://legit.org/profile", content="Dr. Ahmet beyin cerrahıdır.")
    ]
    v, note = _audit_vote(
        vote="DOĞRULANDI",
        evidence_url="https://legit.org/profile",
        evidence_quote="beyin cerrahıdır",
        claim_text="Beyin cerrahı",
        sources=sources,
    )
    assert v == "DOĞRULANDI"
    assert note is None


def test_audit_vote_unentailed_content():
    sources = [
        SimpleNamespace(source_url="https://legit.org/page", content="Hava durumu yarın yağmurlu.")
    ]
    # Claim has no overlap with source content and no matching quote/url
    v, note = _audit_vote(
        vote="DOĞRULANDI",
        evidence_url="",
        evidence_quote="",
        claim_text="Kuantum fizikçisi",
        sources=sources,
    )
    assert v == "BİLİNMİYOR"
    assert note == "kanit_bagi_yetersiz"


class _MockGateway:
    def __init__(self, juror_status: str, evidence_url: str = "", evidence_quote: str = ""):
        self.juror_status = juror_status
        self.evidence_url = evidence_url
        self.evidence_quote = evidence_quote

    def get_agent_chain(self, agent_name, task):
        return ["anthropic/claude-sonnet-5"]

    async def query_json_chain(self, prompt, schema, task="fast", **kwargs):
        agent_name = kwargs.get("agent_name", "")
        if agent_name == "autonomous_verifier_extract":
            return SimpleNamespace(claims=[
                Claim(claim_text="Mimar", category="meslek"),
            ])
        if str(agent_name).startswith("pineal_juror"):
            return VerificationResult(
                claim_text="Mimar",
                truth_status=self.juror_status,
                evidence_url=self.evidence_url,
                evidence_quote=self.evidence_quote,
            )
        raise AssertionError(f"Unexpected agent: {agent_name}")


class _MockSearchEngine:
    tavily_key = "test_key"
    serpapi_key = None
    exa_key = None

    def __init__(self, source_url="https://evidence.org/item", content="Mimar olarak mezun oldu."):
        self.source_url = source_url
        self.content = content

    async def search(self, query, num_results=2):
        return SimpleNamespace(
            available=True,
            results=[SimpleNamespace(source_url=self.source_url, content=self.content)],
        )


@pytest.mark.asyncio
async def test_zero_conclusive_has_zero_confidence_and_fails_closed():
    """Tüm iddialar BİLİNMİYOR ise 0.70 floor uygulanmamalı; 0.0 güven ve fail-closed dönmeli."""
    gw = _MockGateway(juror_status="BİLİNMİYOR")
    search = _MockSearchEngine()
    verifier = AutonomousVerifier(search_engine=search)

    report = await verifier.execute(
        {"target_profile": {"bio": "Mimar", "name": "Ada"}},
        memory=None,
        llm_gateway=gw,
    )

    assert report.status == "UNVERIFIED"
    assert report.confidence == 0.0
    assert report.data_confidence is False
    assert report.fallback_reason == "no_conclusive_evidence"


@pytest.mark.asyncio
async def test_uncertain_votes_block_full_verified_status():
    """Kısmi doğrulama tam 'VERIFIED' olamaz; 'PARTIALLY_VERIFIED' olmalı."""
    class _MultiClaimGateway:
        def get_agent_chain(self, agent_name, task):
            return ["anthropic/claude-sonnet-5"]

        async def query_json_chain(self, prompt, schema, task="fast", **kwargs):
            agent_name = kwargs.get("agent_name", "")
            if agent_name == "autonomous_verifier_extract":
                return SimpleNamespace(claims=[
                    Claim(claim_text="Mimar", category="meslek"),
                    Claim(claim_text="Astronot", category="meslek"),
                ])
            if str(agent_name).startswith("pineal_juror"):
                # Mimar is confirmed, Astronot is unknown
                if "<UNTRUSTED_CLAIM>\nMimar" in prompt:
                    return VerificationResult(
                        claim_text="Mimar",
                        truth_status="DOĞRULANDI",
                        evidence_url="https://evidence.org/item",
                        evidence_quote="Mimar olarak mezun oldu",
                    )
                else:
                    return VerificationResult(
                        claim_text="Astronot",
                        truth_status="BİLİNMİYOR",
                    )
            raise AssertionError(f"Unexpected: {agent_name}")

    search = _MockSearchEngine()
    verifier = AutonomousVerifier(search_engine=search)
    gw = _MultiClaimGateway()

    report = await verifier.execute(
        {"target_profile": {"bio": "Mimar ve astronot", "name": "Ada"}},
        memory=None,
        llm_gateway=gw,
    )

    assert report.status == "PARTIALLY_VERIFIED"
    assert report.overall_authenticity_score == 0.5
    assert report.confidence == 0.5
    assert report.data_confidence is True
