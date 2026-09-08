"""
F3 kontrat testi: UI agent kartlarindaki model etiketleri gateway SoT'sine kilitlenir.

UnifiedCompactPanel.svelte'teki 13 ajan kartinin her biri primaryModel/backupModel
gosterir. SoT = LLMGateway.AGENT_CHAINS uzerine config/task_routing.json delta'sidir
(gateway.get_agent_chain onceliginin env-override'siz hali: task_routing > AGENT_CHAINS;
env override operator-run-time aracidir, kontrat degildir). UI etiketi, zincirin ilk
iki modelinin KISA adidir (registry tam model-id'sinin '/' sonrasi).

Gecmis (2026-09-08 denetimi): passion/cognitive/friction 2026-09-02 karar matrisinde
tasindi (llm_gateway.AGENT_CHAINS) ama UI 6 satirda eski modelleri gosteriyordu
(UI: passion primary claude-sonnet-5; kod: gemini-3.7-flash). Bu test o sapmayi
kilitler: etiket zincirden saparsa KIRMIZI.

Simetrik disiplin: purity_scan.rs gibi kaynak-metin taramasi yapar; frontend'de ayri
test altyapisi yoktur, bu yuzden kontrat Python tarafinda statik okumayla kurulur.
"""
import re
from pathlib import Path

from agent_core.services.llm_gateway import LLMGateway
from agent_core.services.task_routing_resolver import resolve_task_chain

FRONTEND_AGENT_FILE = Path("frontend/src/components/UnifiedCompactPanel.svelte")

# Svelte satirindan id + iki model etiketini cikarir. Her ajan karti tek satirdadir.
ROW_RE = re.compile(
    r'id: "([a-z_]+)"[^\n]*?primaryModel: "([^"]*)"[^\n]*?backupModel: "([^"]*)"'
)

# LLM'siz deterministik ajanlar: model zinciri yoktur; UI rozeti yereldir ve
# gateway'de karsiligi aranmaz.
DETERMINISTIC_ROWS = {
    "resonance_calc": ("local-numpy", "\u2014"),
}

EXPECTED_PANEL_IDS = frozenset({
    "mirror_truth", "autonomous_verifier", "human_behavior", "passion_mapper",
    "friction_detector", "cognitive_profiler", "resonance_calc", "pattern_interrupt",
    "resonance_synthesizer", "vision_analyzer", "osint_investigator",
    "authenticity_auditor", "depth_analyst",
})


def _short(model_id: str) -> str:
    """Registry tam model-id'sinden UI kisa adini uretir (display SoT kurali)."""
    return model_id.rsplit("/", 1)[-1]


def _effective_chain(agent_id: str) -> list[str]:
    """gateway.get_agent_chain'in env-override'siz SoT hali (task_routing > AGENT_CHAINS)."""
    valid_keys = frozenset(LLMGateway.MODEL_REGISTRY.keys())
    routed = resolve_task_chain(agent_id, task="depth", valid_keys=valid_keys)
    if routed is not None:
        return [LLMGateway.MODEL_REGISTRY[key] for key in routed]
    if agent_id in LLMGateway.AGENT_CHAINS:
        return list(LLMGateway.AGENT_CHAINS[agent_id])
    return []


def _parse_rows() -> dict[str, tuple[str, str]]:
    source = FRONTEND_AGENT_FILE.read_text(encoding="utf-8")
    rows: dict[str, tuple[str, str]] = {}
    for line in source.splitlines():
        m = ROW_RE.search(line)
        if m:
            rows[m.group(1)] = (m.group(2), m.group(3))
    return rows


def test_panel_lists_all_thirteen_agents_once():
    rows = _parse_rows()
    assert set(rows) == EXPECTED_PANEL_IDS, (
        f"UI ajan karti kumesi SoT'den sapti: "
        f"fazla={sorted(set(rows) - EXPECTED_PANEL_IDS)} "
        f"eksik={sorted(EXPECTED_PANEL_IDS - set(rows))}"
    )


def test_ui_model_labels_match_gateway_chain_source_of_truth():
    rows = _parse_rows()
    failures = []
    for agent_id, (ui_primary, ui_backup) in sorted(rows.items()):
        if agent_id in DETERMINISTIC_ROWS:
            expected = DETERMINISTIC_ROWS[agent_id]
        else:
            chain = _effective_chain(agent_id)
            if len(chain) < 2:
                failures.append(f"{agent_id}: zincir 2'den kisa ({chain}) - UI 2 slot gosterir")
                continue
            expected = (_short(chain[0]), _short(chain[1]))
        if (ui_primary, ui_backup) != expected:
            failures.append(
                f"{agent_id}: UI ({ui_primary!r}, {ui_backup!r}) != SoT {expected!r}"
            )
    assert not failures, "UI model etiketleri gateway SoT'sinden sapti:\n" + "\n".join(failures)
