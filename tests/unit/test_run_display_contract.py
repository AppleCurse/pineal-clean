"""F2 şeffaflık kontratı — AgentRun serileştirmesi canlı model/via üretir.

(F2) Backend ``AgentRun`` şeması model/via taşımaz; UI "ACTIVE MODEL/VIA"
çubuğu uzun süre statik fallback gösterdi çünkü broadcast iki noktası da bu
alanları HİÇ üretmiyordu. Düzeltme: tek SoT ``_serialize_run_entry`` +
``_run_display_fields`` — gerçek model/provider, ajanın
``output_summary._provenance`` kaydından türetilir (yakalanan çağrıların son
başarılısı). Mutasyon: provenancedan model çekme kaldırılırsa bu dosya KIRMIZI.
"""

from agent_core.domain.memory_models import AgentRun
from backend.api import _run_display_fields, _serialize_run_entry


def _run(prov) -> AgentRun:
    return AgentRun(
        task_id="t1",
        agent_name="pattern_interrupt",
        status="completed",
        output_summary={"_provenance": prov},
        call_ids=["c1"],
    )


def test_llm_provenance_yields_live_model_and_via():
    run = _run({
        "source": "llm",
        "call_id": "c1",
        "model": "openai/gpt-oss-120b",
        "provider": "groq",
    })
    fields = _run_display_fields(run)
    assert fields == {
        "model": "openai/gpt-oss-120b",
        "via": "groq",
        "run_source": "llm",
    }


def test_llm_cache_source_kept():
    run = _run({"source": "llm_cache", "model": "openai/gpt-oss-120b", "provider": "openrouter"})
    assert _run_display_fields(run)["run_source"] == "llm_cache"
    assert _run_display_fields(run)["via"] == "openrouter"


def test_deterministic_source_says_so_not_static_model():
    run = _run({"source": "deterministic", "model": None, "provider": None})
    fields = _run_display_fields(run)
    assert fields["model"] is None
    assert fields["via"] == "deterministik-motor"


def test_fallback_source_is_visible():
    run = _run({"source": "fallback", "fallback_reason": "low_confidence"})
    fields = _run_display_fields(run)
    assert fields["model"] is None
    assert fields["via"] == "fallback:low_confidence"


def test_no_provenance_yields_null_not_static():
    run = AgentRun(task_id="t", agent_name="x", status="failed")
    assert _run_display_fields(run)["model"] is None
    assert _run_display_fields(run)["run_source"] is None


def test_serialize_run_entry_shape_with_timestamps():
    run = _run({"source": "llm", "model": "poolside/laguna-s-2.1:free", "provider": "nous-research"})
    entry = _serialize_run_entry(run, with_timestamps=True)
    assert entry["status"] == "completed"
    assert entry["call_ids"] == ["c1"]
    assert entry["model"] == "poolside/laguna-s-2.1:free"
    assert entry["via"] == "nous-research"
    assert entry["run_source"] == "llm"
    assert entry["started_at"] is None and entry["completed_at"] is None
    assert entry["provenance"]["source"] == "llm"


def test_serialize_run_entry_without_timestamps_omits_them():
    run = _run({"source": "llm", "model": "m", "provider": "openrouter"})
    entry = _serialize_run_entry(run, with_timestamps=False)
    assert "started_at" not in entry
    assert "completed_at" not in entry
