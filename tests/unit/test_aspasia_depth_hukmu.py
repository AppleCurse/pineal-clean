"""ASPASIA + ROUTING HÜKMÜ — derinlik metriklerinin diskten okunmasi.

Kapsam:
  1. extract_depth_digest: muhur cozumu (degerler birebir) + son-muhur
     kazanir + bozuk/eksik muhurde sessizlik (uydurma yok).
  2. SONUÇ satiri: bitmis gorev + kanonik muhur -> telafi/reaksiyon/
     kirilma olgu diliyle satirda (kesin degerler).
  3. HAFIZA-DISK: RAM bosken diskteki muhur okunur; muhur yoksa satir
     derinliksiz kalir (eksik sayi tamamlanmaz).
  4. Idle: RAM+disk bossa ve telemetri ozetinde derinlik iddiasi YOK.
  5. Routing birlikte-yasami: ROUTING/ROUTING-ADAY etiketi derinlik
     satirlariyla celismez (plan gozlem gibi sunulmaz).
  6. Chat promptu: Aspasia LLM'i kesin degerleri gorur.

Dogruluk ilkesi: diskte muhur yoksa Aspasia derinlik KONUSMAZ.
"""

import asyncio
import json as _json
from types import SimpleNamespace

from agent_core.aspasia.aspasia_chief import AspasiaChief
from agent_core.aspasia.interface import (
    DiskMemoryBridge,
    MissionResultReader,
    build_oversight_digest,
    extract_depth_digest,
)
from agent_core.services.canonical_memory import CanonicalMemory


def _depth_doc(comp=0.42, react=0.61, nrup=2,
               kinds=("entropy_jump", "variance_shift"), verdict="ok"):
    return {
        "verdict": verdict,
        "confidence": 0.7,
        "compensation_index": comp,
        "reaction_formation_index": react,
        "epistemic_weights": {"w_staging": 0.5, "w_rhythm": 0.5},
        "channels": {"rhythm": {"signals": {
            "n_ruptures": nrup, "n_regimes": 2,
            "rupture_kinds": list(kinds),
        }}},
        "reason": "tasiyici kanallar: staging, rhythm",
    }


def _sealed_evidence(depth):
    return [
        {"agent": "human_behavior", "result": {"confidence": 0.8}},
        {"agent": "psychodynamic_depth", "evidence_type": "forensic_digest",
         "result": {"depth": depth, "confidence": depth.get("confidence")}},
    ]


def _task_file(task_id, evidence, confidence=0.8):
    return {
        "task_id": task_id, "last_updated": "2026-09-08T00:00:00+00:00",
        "evidence": evidence, "confidence": confidence,
    }


def _disk_executor(tmp_path, files):
    for name, payload in files.items():
        path = tmp_path / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(_json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return SimpleNamespace(memory=CanonicalMemory(storage_path=str(tmp_path)))


class _SilentGW:
    """Routing/kota/maliyet uretmeyen stub: yalniz gorev satirlari kalir."""

    call_log = []

    def get_agent_chain(self, agent, task):
        raise RuntimeError("no chain")

    def budget_status(self):
        raise RuntimeError("no budget")


class _RoutingGW(_SilentGW):
    AGENT_CHAINS = {"friction_detector": ["m1"]}
    MODEL_PRICING = {}
    openrouter_base_url = "https://openrouter.ai/api/v1"

    def __init__(self, call_log):
        self.call_log = call_log

    def get_agent_chain(self, agent, task):
        return ["m1"]

    def agent_route_variants(self, model):
        return [None]


def _finished_room(task_id):
    return {"active_tasks": {task_id: {
        "task_id": task_id, "status": "completed",
        "planned_agents": ["human_behavior"],
        "completed_agents": ["human_behavior"],
        "current_agent": None, "agent_runs": {},
    }}}


# ------------------------------------------------------------------ #
# 1) muhur cozumu
# ------------------------------------------------------------------ #
def test_extract_reads_sealed_values_verbatim():
    digest = extract_depth_digest(_sealed_evidence(_depth_doc()))
    assert digest["compensation_index"] == 0.42
    assert digest["reaction_formation_index"] == 0.61
    assert digest["n_ruptures"] == 2
    assert digest["rupture_kinds"] == ["entropy_jump", "variance_shift"]


def test_extract_last_seal_wins():
    first = _sealed_evidence(_depth_doc(comp=0.10, react=0.10))
    second = _sealed_evidence(_depth_doc(comp=0.42, react=0.61))
    digest = extract_depth_digest(first + second)
    assert digest["compensation_index"] == 0.42


def test_extract_silent_without_usable_seal():
    assert extract_depth_digest([]) is None
    assert extract_depth_digest([{"agent": "x", "result": {}}]) is None
    assert extract_depth_digest("junk") is None
    # verdict ok degilse konusma.
    assert extract_depth_digest(
        _sealed_evidence(_depth_doc(verdict="no_evidence"))) is None
    # Sayisal indeks yoksa konusma (eksik sayi tamamlanmaz).
    broken = _depth_doc()
    del broken["reaction_formation_index"]
    assert extract_depth_digest(_sealed_evidence(broken)) is None
    broken2 = _depth_doc()
    broken2["compensation_index"] = "yuksek"
    assert extract_depth_digest(_sealed_evidence(broken2)) is None


def test_reader_carries_depth_or_none(tmp_path):
    task_id = "op_hukum_1"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, _sealed_evidence(_depth_doc())),
        "op_yalin.json": _task_file("op_yalin", [{"agent": "a", "result": {}}]),
    })
    sealed = MissionResultReader().read(ex, task_id)
    assert sealed["state"] == "ok"
    assert sealed["depth"]["reaction_formation_index"] == 0.61
    plain = MissionResultReader().read(ex, "op_yalin")
    assert plain["state"] == "ok"
    assert plain["depth"] is None


# ------------------------------------------------------------------ #
# 2-3) SONUÇ + HAFIZA-DISK olgu satirlari
# ------------------------------------------------------------------ #
def test_sonuc_line_states_depth_facts_verbatim(tmp_path):
    task_id = "op_hukum_2"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, _sealed_evidence(_depth_doc())),
    })
    digest = build_oversight_digest(_SilentGW(), _finished_room(task_id), ex, None)
    assert "SONUÇ[op_hukum_2]:" in digest
    assert "derinlik: telafi=0.42 reaksiyon=0.61 kırılma=2 [entropy_jump+variance_shift]" in digest


def test_sonuc_without_seal_has_no_depth_claim(tmp_path):
    task_id = "op_hukum_3"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, [{"agent": "a", "result": {}}]),
    })
    digest = build_oversight_digest(_SilentGW(), _finished_room(task_id), ex, None)
    assert "SONUÇ[op_hukum_3]:" in digest
    assert "derinlik" not in digest


def test_disk_bridge_reads_sealed_depth_when_ram_empty(tmp_path):
    task_id = "op_20260908000000_hukum"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, _sealed_evidence(_depth_doc())),
    })
    bridge = DiskMemoryBridge(ex).latest()
    assert bridge["tasks"][0]["depth"]["compensation_index"] == 0.42
    digest = build_oversight_digest(_SilentGW(), {}, ex, None)
    assert "HAFIZA-DISK:" in digest
    assert "derinlik=telafi=0.42 reaksiyon=0.61 kırılma=2 [entropy_jump+variance_shift]" in digest


def test_disk_bridge_without_seal_stays_silent_on_depth(tmp_path):
    task_id = "op_20260908000000_yalin"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, [{"agent": "a", "result": {}}]),
    })
    digest = build_oversight_digest(_SilentGW(), {}, ex, None)
    assert "HAFIZA-DISK:" in digest
    assert "derinlik" not in digest


# ------------------------------------------------------------------ #
# 4) idle sessizligi
# ------------------------------------------------------------------ #
def test_idle_digest_and_telemetry_claim_no_depth(tmp_path):
    ex = _disk_executor(tmp_path, {})
    digest = build_oversight_digest(_SilentGW(), {}, ex, None)
    assert "derinlik" not in digest
    assert "telafi" not in digest
    chief = AspasiaChief(llm_gateway=object())
    assert "derinlik" not in chief.build_telemetry_summary({})
    assert "derinlik" not in chief.build_telemetry_summary(None)


# ------------------------------------------------------------------ #
# 5) routing birlikte-yasami
# ------------------------------------------------------------------ #
def _observed_call():
    return [{
        "call_id": "c1", "agent_id": "friction_detector", "model": "m1",
        "requested_model": "m1", "actual_model": "m1-real", "provider": "groq",
    }]


def test_observed_routing_coexists_with_depth_facts(tmp_path):
    task_id = "op_hukum_4"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, _sealed_evidence(_depth_doc())),
    })
    digest = build_oversight_digest(
        _RoutingGW(_observed_call()), _finished_room(task_id), ex, None)
    assert "ROUTING[friction_detector]" in digest
    assert "ROUTING-ADAY" not in digest
    assert "gozlemlenen=m1-real@groq" in digest
    assert "derinlik: telafi=0.42" in digest


def test_candidate_routing_not_confused_with_depth_facts(tmp_path):
    task_id = "op_20260908000000_hukum2"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, _sealed_evidence(_depth_doc())),
    })
    digest = build_oversight_digest(_RoutingGW([]), {}, ex, None)
    assert "ROUTING-ADAY[friction_detector]" in digest
    assert "henüz çağrı yok" in digest
    assert "derinlik=telafi=0.42" in digest


# ------------------------------------------------------------------ #
# 6) chat promptu kesin degerleri tasir
# ------------------------------------------------------------------ #
def test_chat_prompt_carries_verbatim_depth_values(tmp_path):
    captured = {}

    class _ChatGW(_RoutingGW):
        async def query_chain(self, **kwargs):
            captured.update(kwargs)
            return "Elbette Mösyö."

    task_id = "op_hukum_5"
    ex = _disk_executor(tmp_path, {
        f"{task_id}.json": _task_file(task_id, _sealed_evidence(_depth_doc())),
    })
    chief = AspasiaChief(llm_gateway=_ChatGW([]), executor=ex)
    asyncio.run(chief.chat("son analiz ne diyor?", room_state=_finished_room(task_id)))
    assert "telafi=0.42 reaksiyon=0.61" in captured["prompt"]
    assert "kırılma=2 [entropy_jump+variance_shift]" in captured["prompt"]
