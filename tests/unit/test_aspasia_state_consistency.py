"""FAZ 2 — Aspasia durum/telemetri tutarlilik sozlesmeleri.

B1. Enum repr sizintisi yok: "PipelineStatus.COMPLETED" metni ne API
    status alaninda ne digest/telemetri ozetinde gorunur.
B2. Terminal kumesi api._TERMINAL_PIPELINE_STATES ile senkron: iptal
    gorevler bayat sayilir ve SONUC dongusune girer.
B3. Paylasim-artikli gercek URL'ler (?igsh=, #fragman) kabul edilir;
    lookalike host ve hedefsiz komut yine reddedilir.
B4. Kota statusu lowercase kanonik degerdir ("unknown"/"healthy");
    bilinmeyen kota gozlemlenmis gibi gosterilmez, KOTA gurultu satiri uretmez.
"""

import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent_core.aspasia.aspasia_chief import AspasiaChief
from agent_core.aspasia.interface import (
    AgentInspector,
    AspasiaCommandGateway,
    AspasiaIntent,
    FINAL_TASK_STATUSES,
    MissionResultReader,
    QuotaReader,
    build_oversight_digest,
)
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.services.provider_manager import QuotaSnapshot, QuotaStatus


# ------------------------------------------------------------------ #
# B1. enum repr sizintisi
# ------------------------------------------------------------------ #
def _room_with(status):
    return {"active_tasks": {
        "op_1": SimpleNamespace(
            task_id="op_1", status=status, planned_agents=["human_behavior"],
            completed_agents=[], current_agent="human_behavior", agent_runs={},
        ),
    }}


def test_run_status_normalizes_pipeline_enum():
    st = AgentInspector(None).run_status(_room_with(PipelineStatus.PROCESSING))
    assert st["status"] == "processing"
    assert st["is_final"] is False
    assert "PipelineStatus" not in str(st)


def test_run_status_final_enum_is_final():
    st = AgentInspector(None).run_status(_room_with(PipelineStatus.COMPLETED))
    assert st["status"] == "completed"
    assert st["is_final"] is True


def test_telemetry_summary_never_shows_enum_repr():
    chief = AspasiaChief(llm_gateway=MagicMock())
    text = chief.build_telemetry_summary(_room_with(PipelineStatus.COMPLETED))
    assert "Durum: completed" in text
    assert "PipelineStatus" not in text


def test_telemetry_summary_dict_snapshot_with_enum():
    chief = AspasiaChief(llm_gateway=MagicMock())
    room = {"active_tasks": {"op_2": {
        "task_id": "op_2", "status": PipelineStatus.HALTED_CRITICAL,
        "planned_agents": [], "completed_agents": [], "current_agent": None,
        "halted_reason": "x", "agent_runs": {},
    }}}
    text = chief.build_telemetry_summary(room)
    assert "halted_critical" in text
    assert "PipelineStatus" not in text


# ------------------------------------------------------------------ #
# B2. terminal kumesi senkronu
# ------------------------------------------------------------------ #
def test_terminal_sets_stay_in_sync_with_api():
    from backend.api import _TERMINAL_PIPELINE_STATES

    assert set(FINAL_TASK_STATUSES) == set(_TERMINAL_PIPELINE_STATES)


def test_cancelled_task_is_final_not_live():
    st = AgentInspector(None).run_status(_room_with("cancelled"))
    assert st["is_final"] is True
    st2 = AgentInspector(None).run_status(_room_with("halted_user"))
    assert st2["is_final"] is True


def test_latest_finished_finds_cancelled_task():
    room = {"active_tasks": {
        "op_old": SimpleNamespace(task_id="op_old", status="processing"),
        "op_cancel": SimpleNamespace(task_id="op_cancel", status="cancelled"),
    }}
    assert MissionResultReader.latest_finished_task_id(room) == "op_cancel"


# ------------------------------------------------------------------ #
# B3. paylasim URL normalizasyonu
# ------------------------------------------------------------------ #
class _IntentGW:
    """Niyet cikarimini konserve AspasiaIntent ile donduren sahte gateway."""

    def __init__(self, intent):
        self._intent = intent

    def capture_calls(self, task_id, agent_id):
        return contextlib.nullcontext()

    async def query_json_chain(self, **kwargs):
        return self._intent


async def _submit(url):
    launched = []
    intent = AspasiaIntent(
        intent="run_profile_analysis", target_url=url, rationale="test",
        goals=["profile_analysis"],
    )
    gw = _IntentGW(intent)
    commands = AspasiaCommandGateway(
        dispatch=lambda spec: launched.append(spec) or "op_test_1", gateway=gw,
    )
    result = await commands.submit("su profili analiz et", client_id="c1")
    return result, launched


async def test_share_url_with_tracking_params_is_accepted():
    result, launched = await _submit("https://www.instagram.com/hedef/?igsh=abc123&hl=tr")
    assert result.accepted and result.task_id == "op_test_1"
    # Dispatch'e temiz URL gider (asagi akis ayni hedefi gorur).
    assert launched and launched[0]["target_url"] == "https://www.instagram.com/hedef/"


async def test_share_url_with_fragment_is_accepted():
    result, launched = await _submit("https://instagram.com/hedef#fragman")
    assert result.accepted
    assert launched[0]["target_url"] == "https://instagram.com/hedef"


async def test_lookalike_host_and_missing_target_still_rejected():
    result, launched = await _submit("https://instagram.example.com/victim/?igsh=x")
    assert not result.accepted and result.reason == "unsupported_or_missing_target"
    result2, launched2 = await _submit("")
    assert not result2.accepted and result2.reason == "unsupported_or_missing_target"
    assert launched == [] and launched2 == []


# ------------------------------------------------------------------ #
# B4. kota status kanonik degeri
# ------------------------------------------------------------------ #
class _FakeGov:
    def __init__(self, status):
        self._status = status

    def snapshot(self, provider, model=None):
        return QuotaSnapshot(status=self._status, source="test")


class _QuotaGW:
    """Quota disinda hicbir gercek veri uretmeyen sahte gateway."""

    def __init__(self, quota_status):
        self.call_log = []
        self._quota_status = quota_status

    def get_agent_chain(self, agent, task):
        raise RuntimeError("no chain")

    def budget_status(self):
        raise RuntimeError("no budget")

    def _quota_governor(self):
        return _FakeGov(self._quota_status)


def test_quota_reader_returns_lowercase_canonical_status():
    assert QuotaReader(governor=_FakeGov(QuotaStatus.HEALTHY)).snapshot("groq")["status"] == "healthy"
    assert QuotaReader(governor=_FakeGov(QuotaStatus.UNKNOWN)).snapshot("groq")["status"] == "unknown"


def test_digest_omits_quota_line_when_nothing_observed():
    digest = build_oversight_digest(_QuotaGW(QuotaStatus.UNKNOWN), None, None, None)
    assert digest == ""
    assert "KOTA" not in digest


def test_digest_shows_quota_line_when_observed():
    digest = build_oversight_digest(_QuotaGW(QuotaStatus.HEALTHY), None, None, None)
    assert "KOTA: groq:healthy | cerebras:healthy" in digest


# ------------------------------------------------------------------ #
# B5. aday rota gozlemlenmis gercek gibi sunulmaz (halusinasyon kilidi)
# ------------------------------------------------------------------ #
class _RoutingGW:
    """ROUTING satiri icin minimal stub; call_log ile oynanabilir."""

    AGENT_CHAINS = {"friction_detector": ["m1"]}
    MODEL_PRICING = {}
    openrouter_base_url = "https://openrouter.ai/api/v1"

    def __init__(self, call_log):
        self.call_log = call_log

    def get_agent_chain(self, agent, task):
        return ["m1"]

    def agent_route_variants(self, model):
        return [None]

    def budget_status(self):
        raise RuntimeError("no budget")


def test_idle_digest_labels_routing_as_candidate():
    digest = build_oversight_digest(_RoutingGW([]), None, None, None)
    assert "ROUTING-ADAY[friction_detector]" in digest
    assert "henüz çağrı yok" in digest
    assert "ROUTING[friction_detector]" not in digest


def test_digest_after_observed_call_states_fact():
    call_log = [{
        "call_id": "c1", "agent_id": "friction_detector", "model": "m1",
        "requested_model": "m1", "actual_model": "m1-real",
        "provider": "groq",
    }]
    digest = build_oversight_digest(_RoutingGW(call_log), None, None, None)
    assert "ROUTING[friction_detector]" in digest
    assert "ROUTING-ADAY" not in digest
    assert "gozlemlenen=m1-real@groq" in digest


def test_chat_instruction_distinguishes_candidate_from_observed():
    captured = {}

    class _ChatGW(_RoutingGW):
        async def query_chain(self, **kwargs):
            captured.update(kwargs)
            return "Elbette Mösyö."

    chief = AspasiaChief(llm_gateway=_ChatGW([]))
    import asyncio
    asyncio.run(chief.chat("routing neden boyle?", room_state=None))
    prompt = captured["prompt"]
    assert "ROUTING-ADAY" in prompt
    assert "PLANLANAN" in prompt
    assert "GÖZLEMLENMİŞ" in prompt
