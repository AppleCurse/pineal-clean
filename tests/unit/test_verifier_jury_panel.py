"""[BOSS-4] Çapraz jüri paneli — kural artık kodda.

Röntgen bulgusu: README ve UI "3 farklı model ailesinden jüri; üreten model kendi
çıktısını onaylayamaz; Claude jüriden otomatik çıkarılır" diyordu; kodda ise tek
zincir çağrısı vardı (autonomous_verifier → Claude). Jüri rotaları yalnız sözlükte
duruyordu. Bu dosya kuralı kilitler.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_core.agents.autonomous_verifier import AutonomousVerifier, VerificationResult, VerifierReport
from agent_core.services.llm_gateway import LLMGateway, model_family

PROMPT = "<UNTRUSTED_CLAIM>x</UNTRUSTED_CLAIM>"


class _PanelGateway:
    """Q Şemasına göre yanıt veren sahte gateway (çağrıları kaydeder)."""

    def __init__(self, producer_model: str = "anthropic/claude-sonnet-5", verdicts: dict | None = None,
                 extract_claims: list | None = None):
        self.producer_model = producer_model
        self.verdicts = verdicts or {}
        self.extract_claims = extract_claims or []
        self.calls: list[str] = []

    def get_agent_chain(self, agent_name, task):
        if agent_name == "autonomous_verifier":
            return [self.producer_model]
        raise KeyError(agent_name)

    async def query_json_chain(self, prompt, schema, task="depth", **kwargs):
        agent_name = kwargs.get("agent_name")
        self.calls.append(agent_name or f"task:{task}")
        if agent_name == "autonomous_verifier_extract":
            from agent_core.agents.autonomous_verifier import Claim

            return SimpleNamespace(claims=[Claim(claim_text=c, category="meslek") for c in self.extract_claims])
        if str(agent_name).startswith("pineal_juror"):
            status = self.verdicts.get(agent_name, "BİLİNMİYOR")
            return VerificationResult(
                claim_text="x", truth_status=status, evidence_url=f"https://{agent_name}.test"
            )
        raise AssertionError(f"beklenmeyen çağrı: {agent_name}")


class _FakeSearch:
    tavily_key = "k"
    serpapi_key = None
    exa_key = None

    async def search(self, query, num_results=2):
        return SimpleNamespace(
            available=True,
            results=[SimpleNamespace(source_url="https://kanit.test", content="stratejist olduğu yazıyor")],
        )


@pytest.mark.asyncio
async def test_panel_asks_all_seats_when_producer_family_unknown():
    gw = _PanelGateway(producer_model="", verdicts={})  # aile bilinmiyor
    verifier = AutonomousVerifier(search_engine=_FakeSearch())

    result = await verifier._verify_with_panel(PROMPT, "Stratejist", gw)

    assert sorted(gw.calls) == sorted(AutonomousVerifier.PANEL_AGENTS)
    assert result.dropped_juror == []
    assert result.truth_status == "BİLİNMİYOR"  # tüm koltuklar BİLİNMİYOR oyu verdi


@pytest.mark.asyncio
async def test_producing_family_seat_is_dropped():
    """Üreten Claude ise Claude koltuğu karar anında düşer (kendi çıktısını onaylayamaz)."""
    gw = _PanelGateway(verdicts={"pineal_juror_google": "DOĞRULANDI", "pineal_juror_open": "BİLİNMİYOR"})
    verifier = AutonomousVerifier(search_engine=_FakeSearch())

    result = await verifier._verify_with_panel(PROMPT, "Stratejist", gw)

    assert "pineal_juror_claude" in result.dropped_juror
    assert "pineal_juror_claude" not in gw.calls, "düşürülen koltuk yine de çağrıldı"
    assert set(result.juror_votes) == {"pineal_juror_google", "pineal_juror_open"}


@pytest.mark.asyncio
async def test_majority_rule_decides_with_two_seats():
    gw = _PanelGateway(verdicts={"pineal_juror_google": "YALAN", "pineal_juror_open": "YALAN"})
    verifier = AutonomousVerifier(search_engine=_FakeSearch())

    result = await verifier._verify_with_panel(PROMPT, "Stratejist", gw)

    assert result.truth_status == "YALAN"
    assert result.decision_rule == "panel_cogunluk"
    assert len(result.juror_votes) == 2


@pytest.mark.asyncio
async def test_tie_is_honestly_unknown():
    gw = _PanelGateway(verdicts={"pineal_juror_google": "DOĞRULANDI", "pineal_juror_open": "YALAN"})
    verifier = AutonomousVerifier(search_engine=_FakeSearch())

    result = await verifier._verify_with_panel(PROMPT, "Stratejist", gw)

    assert result.truth_status == "BİLİNMİYOR"
    assert result.decision_rule == "panel_berabere"


@pytest.mark.asyncio
async def test_no_independent_seat_never_approves(monkeypatch):
    """Panelde bağımsız koltuk kalmadıysa ONAY üretilmez."""
    monkeypatch.setattr(
        AutonomousVerifier, "PANEL_AGENTS", ("pineal_juror_claude",)
    )
    gw = _PanelGateway(verdicts={"pineal_juror_claude": "DOĞRULANDI"})
    verifier = AutonomousVerifier(search_engine=_FakeSearch())

    result = await verifier._verify_with_panel(PROMPT, "Stratejist", gw)

    assert result.truth_status == "BİLİNMİYOR"
    assert result.decision_rule == "panel_bagimsiz_uyesi_yok"
    assert gw.calls == [], "üreten aile kendi kararını yine de verdi"


@pytest.mark.asyncio
async def test_full_run_records_jury_evidence_in_report():
    gw = _PanelGateway(
        verdicts={"pineal_juror_google": "DOĞRULANDI", "pineal_juror_open": "DOĞRULANDI"},
        extract_claims=["Kıdemli Stratejist"],
    )
    verifier = AutonomousVerifier(search_engine=_FakeSearch())

    report = await verifier.execute({"target_profile": {"bio": "Kıdemli Stratejist", "name": "Ada"}}, None, gw)

    assert isinstance(report, VerifierReport)
    assert report.status == "VERIFIED"
    assert set(report.jurors) == {"pineal_juror_google", "pineal_juror_open"}
    assert report.dropped_juror == ["pineal_juror_claude"]
    assert "üreten_aile=anthropic" in report.decision_rule
    claim = report.verifications[0]
    assert claim.juror_votes == {"pineal_juror_google": "DOĞRULANDI", "pineal_juror_open": "DOĞRULANDI"}


def test_jury_seats_are_real_routes_with_single_model_and_tier():
    """Jüri koltukları uydurma isim değil: zincir + tier + aile kaydı olmalı."""
    gateway = LLMGateway()
    for seat in LLMGateway.JURY_PANEL_AGENTS:
        chain = gateway.get_agent_chain(seat, "depth")
        assert chain == [LLMGateway.MODEL_REGISTRY[seat]], seat
        assert model_family(chain[0]) != "unknown", seat
    assert model_family(LLMGateway.MODEL_REGISTRY["pineal_juror_claude"]) == "anthropic"
    assert model_family(LLMGateway.MODEL_REGISTRY["pineal_juror_google"]) == "google"

    snapshot = gateway.effective_routing_snapshot()
    untiered = [v for v in snapshot["tier_violations"] if v["rule"] == "untiered"]
    assert untiered == []
    for seat in LLMGateway.JURY_PANEL_AGENTS:
        assert snapshot["tiers"][seat]["tier"] == "jury"
