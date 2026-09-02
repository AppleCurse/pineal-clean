"""Fail-closed usage settlement regressions (audit finding: spend-cap bypass).

Sözleşme: ücretli bir yanıt, güvenilir ``usage`` taşımıyorsa (None, eksik,
negatif, kesirli, bool, sıfır toplam) ayrılan rezervasyon HARCANMIŞ kabul
edilir — asla 0.0'a sıfırlanmaz. Aksi hâlde ``spend_usd += 0`` ile harcama
tavanı delinir.

Kod karşılığı: ``LLMGateway._usage_tokens`` + ``LLMGateway._settle_budget``.
"""

import pytest

from agent_core.services.llm_gateway import LLMGateway


class _Usage:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class _Choice:
    message = type("Message", (), {"content": "ok"})()


class _Response:
    def __init__(self, usage):
        self.usage = usage
        self.choices = [_Choice()]


class _NoUsageCompletions:
    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return _Response(usage=None)


class _Client:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


def _paid_gateway(monkeypatch, completions) -> LLMGateway:
    monkeypatch.setenv("LIVE_LLM_E2E", "1")
    monkeypatch.setenv("OPENROUTER_MAX_SPEND_USD", "1.0")
    monkeypatch.setenv("OPENROUTER_MAX_OUTPUT_TOKENS", "1000")
    monkeypatch.delenv("USE_LOCAL_LLM", raising=False)
    gateway = LLMGateway()
    gateway.client = _Client(completions)
    gateway.cache = None
    return gateway


def _settle(gateway, usage, *, pricing=None, amount=0.5):
    call_id = "op_settle"
    with gateway._budget_lock:
        gateway._budget_reservations[call_id] = amount
        gateway._reserved_spend_usd = amount
    return gateway._settle_budget(call_id, "upstage/solar-pro4", usage, pricing)


UNTRUSTWORTHY_USAGES = [
    pytest.param(None, id="usage-none"),
    pytest.param(_Usage(), id="usage-empty"),
    pytest.param(_Usage(prompt_tokens=-5, completion_tokens=10), id="negative-prompt"),
    pytest.param(_Usage(prompt_tokens=10, completion_tokens=-5), id="negative-completion"),
    pytest.param(_Usage(prompt_tokens=1.5, completion_tokens=2.0), id="fractional"),
    pytest.param(_Usage(prompt_tokens=True, completion_tokens=False), id="boolean-tokens"),
    pytest.param(_Usage(prompt_tokens="1000", completion_tokens="500"), id="string-tokens"),
    pytest.param(_Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=0), id="explicit-zero-total"),
    pytest.param(_Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=-1), id="negative-total"),
    pytest.param(_Usage(prompt_tokens=0, completion_tokens=0), id="zero-sum"),
]


@pytest.mark.parametrize("usage", UNTRUSTWORTHY_USAGES)
def test_untrustworthy_usage_retains_full_reservation(usage):
    gateway = LLMGateway()
    amount = 0.5

    settled = _settle(gateway, usage, amount=amount)

    assert settled == pytest.approx(amount)
    assert gateway.spend_usd == pytest.approx(amount)
    assert gateway.total_cost == pytest.approx(amount)
    assert gateway._reserved_spend_usd == pytest.approx(0.0)
    assert gateway._budget_reservations == {}


def test_trustworthy_usage_settles_observed_cost_instead_of_reservation():
    gateway = LLMGateway()
    usage = _Usage(prompt_tokens=1000, completion_tokens=500)
    pricing = {"in": 2.0, "out": 10.0}  # (1000*2 + 500*10)/1e6 = 0.007

    settled = _settle(gateway, usage, pricing=pricing, amount=0.5)

    assert settled == pytest.approx(0.007)
    assert gateway.spend_usd == pytest.approx(0.007)
    assert gateway._reserved_spend_usd == pytest.approx(0.0)
    assert gateway._budget_reservations == {}


@pytest.mark.asyncio
async def test_paid_call_without_usage_keeps_reserved_cost(monkeypatch):
    """Uçtan uca: sağlayıcı içerik döner ama usage vermezse rezervasyon harcanır."""
    completions = _NoUsageCompletions()
    gateway = _paid_gateway(monkeypatch, completions)

    assert await gateway.query("prompt", model="upstage/solar-pro4") == "ok"

    assert gateway.spend_usd > 0.0  # 0'a sıfırlanmadı
    assert gateway._reserved_spend_usd == pytest.approx(0.0)
    assert gateway._budget_reservations == {}
    assert gateway.call_log[-1]["cost_usd"] > 0.0