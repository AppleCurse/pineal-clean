"""FAZ-1 (b'') — tier-gate DENETİM kilitleri (mechanism-only + audit).

(b'') kararı: ajânın tier'ı zincir veri-modeline gömülmez; contextvar
``_active_agent_tier`` ile variant katmanına taşınır. get_agent_chain SET
eder (agent_tiers.json), agent_route_variants OKUR.

FAZ-1 kuralları (bu dosyada KİLİTLENEN):
- KIRILMA YASAĞI: hard-gate AUDIT modunda. Denetim izi FAZ-2-ENFORCE
  kararlarını UYGULAMADAN yazar; üretim merdiveni birebir korunur.
- T1-revize: audit-doğruluğu + sıralama-doğruluğu kilitleri (mechanism-only).
- T7: sıralı resolve->query'de tier doğruluğu + snapshot sonrası artık-değer
  yokluğu (M-C3: snapshot sonrası tier kalıntısı bırak -> KIRMIZI).

Regresyon kilitleri (bu turun dokunmadığı mevcut davranışlar, ayrı suite'ler):
T2 heavy_cheapest_first (cost ladder), T3 escalation_master (paid firewall),
T4 vision_direct_first, T5 taskgroups_resolved, T6 shadows_fresh.
"""

import asyncio

import pytest

from agent_core.services.llm_gateway import (
    GatewayRoute,
    LLMGateway,
    _active_agent_tier,
    _AGENT_DIRECT_PROVIDER_KEYS,
    _DIAGNOSTIC_ONLY_PROVIDERS,
)


def _key_envs():
    envs = [env for _, env in _AGENT_DIRECT_PROVIDER_KEYS]
    envs += [env for _, env in _DIAGNOSTIC_ONLY_PROVIDERS]
    for pid, _ in _AGENT_DIRECT_PROVIDER_KEYS:
        envs.append("PINEAL_PROVIDER_MODELS_" + pid.upper().replace("-", "_"))
    envs += [
        "OPENROUTER_API_KEY",
        "PINEAL_ALLOW_PAID_ESCALATION",
        "PINEAL_ALLOW_UNPRICED_MODELS",
        "OPENROUTER_MAX_SPEND_USD",
        "PINEAL_AGENT_TIERS_PATH",
        "OPENROUTER_AGENT_CHAIN_PATTERN_INTERRUPT",
        "OPENROUTER_AGENT_CHAIN_SANAL_AJAN_YOK",
        "OPENROUTER_CHAIN_DIALOGUE",
        "OPENROUTER_CHAIN_DEPTH",
        "LIVE_LLM_E2E",
        "PINEAL_ROUTER_LIVE",
    ]
    return envs


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in _key_envs():
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _clean_tier_context():
    """Her test None-tier ile başlar; contextvar kalıntısı testler arası sızmaz."""
    token = _active_agent_tier.set(None)
    try:
        yield
    finally:
        _active_agent_tier.reset(token)


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# T7 — contextvar: get_agent_chain set eder (overwrite), ajan yoksa None yazar
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        ("pattern_interrupt", "simple"),
        ("autonomous_verifier_extract", "simple"),
        ("friction_detector", "heavy"),
        ("depth_analyst", "heavy"),
        ("aspasia", "heavy"),
        ("vision_analyzer", "vision"),
        ("autonomous_verifier", "verify"),
    ],
)
def test_t7_get_agent_chain_sets_tier_context(agent, expected, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    gw.get_agent_chain(agent, "dialogue")
    assert _active_agent_tier.get() == expected


def test_t7_unknown_agent_sets_unknown_tier(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    gw.get_agent_chain("sanal_ajan_yok", "depth")
    assert _active_agent_tier.get() == "unknown"


def test_t7_no_agent_overwrites_stale_tier(monkeypatch):
    """Overwrite disiplini: ajan yoksa None yazılır — stale tier sızmaz."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    gw.get_agent_chain("pattern_interrupt", "dialogue")
    assert _active_agent_tier.get() == "simple"
    gw.get_agent_chain(None, "depth")
    assert _active_agent_tier.get() is None


# --------------------------------------------------------------------------- #
# T7 — snapshot sonrası kalıntı yok (M-C3), çağrıcı değeri korunur
# --------------------------------------------------------------------------- #
def test_t7_snapshot_leaves_no_tier_residue(monkeypatch):
    """M-C3: snapshot döngüsü 18 ajan resolve eder; son yazan tier ÇAĞRICI
    context'ine sızmamalı. Reset kaldırılırsa (mutasyon) son ajanın tier'ı
    (vision_analyzer -> "vision") kalır ve bu test KIRMIZI olur."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    assert _active_agent_tier.get() is None
    gw.effective_routing_snapshot()
    assert _active_agent_tier.get() is None


def test_t7_snapshot_preserves_caller_tier_value(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()
    token = _active_agent_tier.set("simple")
    try:
        gw.effective_routing_snapshot()
        assert _active_agent_tier.get() == "simple"
    finally:
        _active_agent_tier.reset(token)


# --------------------------------------------------------------------------- #
# T7 — telemetri: kararda kullanılan tier chain_source yanına yazılır
# --------------------------------------------------------------------------- #
def test_t7_telemetry_tier_next_to_chain_source(monkeypatch):
    """Gerçek query_chain yolu (gate kapalı): kayıtta chain_source ==
    agent_matrix VE agent_tier == simple; denetim izi ajan hint'ini taşır."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    gw = LLMGateway()

    async def go():
        try:
            await gw.query_chain("selam", task="dialogue", agent_name="pattern_interrupt")
        except RuntimeError as exc:
            assert "REAL_LLM_CALL_NOT_EXECUTED" in str(exc)

    run(go())
    assert gw.call_log, "gate kapalıyken bile çağrı kaydı yazılmalı"
    last = gw.call_log[-1]
    assert last["chain_source"] == "agent_matrix"
    assert last["agent_tier"] == "simple"
    assert gw.tier_audit_trail(), "query yolu denetim izine yazmalı"
    assert gw.tier_audit_trail()[-1]["agent"] == "pattern_interrupt"


# --------------------------------------------------------------------------- #
# T1-revize — audit-doğruluğu: simple zincir statik golden (M-C1 KIRMIZI)
# --------------------------------------------------------------------------- #
def test_t1_audit_simple_chain_static_golden(monkeypatch):
    """pattern_interrupt (simple) zinciri: claude + gemini — İKİSİ DE bugün
    ücretli taşımalarla yürür. FAZ-1 bunları hâlâ TEKLİF eder (kırılma yasağı)
    ama her taşımayı would_deny=simple_non_free ile DENETİM izine yazar.

    M-C1: zincire ücretli üçüncü model eklenirse model kümesi golden'dan
    sapar -> KIRMIZI."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("NOUS_API_KEY", "nk")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    chain = gw.get_agent_chain("pattern_interrupt", "dialogue")
    assert chain == [
        "anthropic/claude-sonnet-5",
        "google/gemini-3.7-flash",
    ]
    # Üretim merdiveni DEĞİŞMEZ: claude -> [nous indirimli, OR legacy]
    ladder = gw.agent_route_variants("anthropic/claude-sonnet-5")
    nous = [v for v in ladder if isinstance(v, GatewayRoute) and v.provider_id == "nous-research"]
    assert len(nous) == 1 and nous[0].input_per_million_usd == pytest.approx(1.6)
    assert None in ladder  # legacy OR hâlâ merdivende (FAZ-1'de deny YOK)
    for model in chain:
        gw.agent_route_variants(model)

    trail = gw.tier_audit_trail()
    models = sorted({e["model"] for e in trail})
    assert models == ["anthropic/claude-sonnet-5", "google/gemini-3.7-flash"]
    assert sorted({e["route_key"] for e in trail}) == [
        "anthropic/claude-sonnet-5@nous-research",
        "anthropic/claude-sonnet-5@openrouter",
        "google/gemini-3.7-flash@openrouter",
    ]
    for entry in trail:
        assert entry["tier"] == "simple"
        assert entry["would_deny"] is True
        assert entry["reason"] == "simple_non_free"
        assert entry["tier_unresolved"] is False


# --------------------------------------------------------------------------- #
# T1-revize — audit-doğruluğu: heavy indirimli FAZ-2'de izin olur (görünür)
# --------------------------------------------------------------------------- #
def test_t1_audit_heavy_discounted_visible_but_firewall_unchanged(monkeypatch):
    """friction_detector (heavy), escalation KAPALI. Bugünkü davranış:
    nous firewall'dan düşer, merdiven [None]. Denetim izi FAZ-2 gerçeğini
    gösterir: nous indirimli -> allow heavy_discounted (escalation istemez),
    OR legacy (liste fiyatı) -> would_deny heavy_listed_gate."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("NOUS_API_KEY", "nk")
    gw = LLMGateway()
    gw.get_agent_chain("friction_detector", "dialogue")
    assert gw.agent_route_variants("anthropic/claude-sonnet-5") == [None]

    trail = gw.tier_audit_trail()
    by_key = {e["route_key"]: e for e in trail}
    assert by_key["anthropic/claude-sonnet-5@nous-research"]["decision"] == "allow"
    assert by_key["anthropic/claude-sonnet-5@nous-research"]["reason"] == "heavy_discounted"
    assert by_key["anthropic/claude-sonnet-5@openrouter"]["would_deny"] is True
    assert by_key["anthropic/claude-sonnet-5@openrouter"]["reason"] == "heavy_listed_gate"
    assert all(e["tier"] == "heavy" for e in trail)


# --------------------------------------------------------------------------- #
# T1-revize — audit-doğruluğu: unknown tier -> heavy-eşdeğeri + unresolved
# --------------------------------------------------------------------------- #
def test_t1_audit_unknown_tier_heavy_equivalent_with_unresolved_marker(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("NOUS_API_KEY", "nk")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")

    # Aynı model (claude) üzerinden: unknown tier kararları heavy-eşdeğeri
    # OLMALI, tek fark tier değeri + tier_unresolved işareti.
    gw_heavy = LLMGateway()
    gw_heavy.get_agent_chain("friction_detector", "dialogue")
    gw_heavy.agent_route_variants("anthropic/claude-sonnet-5")

    gw_unknown = LLMGateway()
    gw_unknown.get_agent_chain("sanal_ajan_yok", "depth")
    gw_unknown.agent_route_variants("anthropic/claude-sonnet-5")

    heavy_ctx = {
        (e["model"], e["route_key"], e["decision"], e["reason"])
        for e in gw_heavy.tier_audit_trail()
    }
    unknown_ctx = {
        (e["model"], e["route_key"], e["decision"], e["reason"])
        for e in gw_unknown.tier_audit_trail()
    }
    assert heavy_ctx  # boşsa kilit süsdür
    assert unknown_ctx == heavy_ctx  # unknown -> heavy-eşdeğeri kararlar
    assert all(e["tier"] == "unknown" and e["tier_unresolved"] for e in gw_unknown.tier_audit_trail())


# --------------------------------------------------------------------------- #
# T1-revize — audit-doğruluğu: tier bağlamı yoksa iz YOK (mekanizma kapalı)
# --------------------------------------------------------------------------- #
def test_t1_audit_inert_without_agent_context(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("NOUS_API_KEY", "nk")
    monkeypatch.setenv("PINEAL_ALLOW_PAID_ESCALATION", "1")
    gw = LLMGateway()
    assert _active_agent_tier.get() is None
    gw.agent_route_variants("anthropic/claude-sonnet-5")
    assert gw.tier_audit_trail() == []


# --------------------------------------------------------------------------- #
# T1-revize — sıralama-doğruluğu: saf karar matrisi (mechanism-only)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("tier", "free", "discounted", "escalation", "decision", "reason", "would_deny", "unresolved"),
    [
        # free her katmanda izin
        ("simple", True, False, False, "allow", "free_transport", False, False),
        ("heavy", True, False, False, "allow", "free_transport", False, False),
        ("unknown", True, False, False, "allow", "free_transport", False, True),
        # simple: non-free -> HARD DENY (indirimli de olsa)
        ("simple", False, True, True, "would_deny", "simple_non_free", True, False),
        ("simple", False, False, True, "would_deny", "simple_non_free", True, False),
        # heavy: indirimli -> default izin (escalation gerekmez)
        ("heavy", False, True, False, "allow", "heavy_discounted", False, False),
        ("heavy", False, True, True, "allow", "heavy_discounted", False, False),
        # heavy: liste fiyatı -> escalation kapısı
        ("heavy", False, False, False, "would_deny", "heavy_listed_gate", True, False),
        ("heavy", False, False, True, "allow", "heavy_listed_escalated", False, False),
        # vision/verify: heavy ailesi davranışı
        ("vision", False, False, False, "would_deny", "heavy_listed_gate", True, False),
        ("verify", False, True, False, "allow", "heavy_discounted", False, False),
        # unknown: heavy-eşdeğeri + tier_unresolved işareti
        ("unknown", False, True, False, "allow", "heavy_discounted", False, True),
        ("unknown", False, False, False, "would_deny", "heavy_listed_gate", True, True),
    ],
)
def test_t1_decision_matrix(
    tier, free, discounted, escalation, decision, reason, would_deny, unresolved
):
    out = LLMGateway._tier_route_decision(
        tier, free=free, discounted=discounted, escalation_enabled=escalation
    )
    assert out["decision"] == decision
    assert out["reason"] == reason
    assert out["would_deny"] is would_deny
    assert out["tier_unresolved"] is unresolved
    assert out["price_class"] in ("free", "discounted", "list")


# --------------------------------------------------------------------------- #
# T1-revize — sıralama-doğruluğu: saf sort-key (mechanism-only, FAZ-2'de uygulanır)
# --------------------------------------------------------------------------- #
def test_t1_sort_key_vision_direct_first():
    """vision: doğrudan taşıma OpenRouter legacy'den ÖNCE — fiyatı yüksek
    olsa bile (direct-first). Ağırlıklar ters çevrilirse KIRMIZI."""
    direct = LLMGateway._tier_variant_sort_key("vision", is_legacy_or=False, price_sum=9.0)
    legacy = LLMGateway._tier_variant_sort_key("vision", is_legacy_or=True, price_sum=0.5)
    assert direct < legacy


def test_t1_sort_key_default_price_first_then_direct():
    """Diğer tier'lar/None: bugünkü maliyet merdiveni (fiyat, sonra direct
    ayraç) birebir korunur."""
    for tier in (None, "heavy", "simple", "unknown"):
        cheap = LLMGateway._tier_variant_sort_key(tier, is_legacy_or=False, price_sum=0.5)
        pricy = LLMGateway._tier_variant_sort_key(tier, is_legacy_or=False, price_sum=9.0)
        assert cheap < pricy
        # eşit fiyatta doğrudan, legacy'den önce (bugünkü davranış)
        direct = LLMGateway._tier_variant_sort_key(tier, is_legacy_or=False, price_sum=1.0)
        legacy = LLMGateway._tier_variant_sort_key(tier, is_legacy_or=True, price_sum=1.0)
        assert direct < legacy
