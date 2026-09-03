"""G7 release-gates workflow yerlesim ve govde sozlesmesi.

Kok neden (2026-09-02 SON_HUKUM_DENETIM / GENEL_DURUM_HARITASI G7-A):
`release-gates.yml` yalnizca `release/` altindaydi. GitHub `workflow_dispatch`
ileri, `on:` anahtari default branch'in `.github/workflows/` dizinindeki
dosyalardan okundugu icin iki canli gate HIC kosulamadi — "yeşil koşu kaydı"
olmadigi icin kapali sayildi. Bu test ayni kaymanin tekrarlanmasini onler.

Yorum/discipline: `on:` YAML 1.1'de `True` anahtarina cevrilir; test bilerek
ham metin (regex/astariz) uzerinden dogrular — YAML parser davranisina bagimli
degil, boylece ek test bagimliligi de gerektirmez.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "release" / "release-gates.yml"
DEPLOYED = REPO_ROOT / ".github" / "workflows" / "release-gates.yml"


def _text(path: Path) -> str:
    assert path.exists(), f"workflow dosyasi bulunamadi: {path}"
    return path.read_text(encoding="utf-8")


def test_release_gates_workflow_is_deployed_to_github_workflows():
    """Dosya `.github/workflows/` altinda OLMALI; yoksa gate'ler kosulamaz."""
    assert DEPLOYED.exists(), (
        ".github/workflows/release-gates.yml yok — Gate A/B dispatch edilemez. "
        "`cp release/release-gates.yml .github/workflows/release-gates.yml`"
    )


def test_deployed_workflow_mirrors_canonical_body_exactly():
    """Kopya ile kaynak birebir ayni olmali (ic bakim kopyasi → kaymasini onler)."""
    assert DEPLOYED.read_bytes() == CANONICAL.read_bytes(), (
        ".github/workflows/release-gates.yml, release/release-gates.yml ile "
        "birebir ayni degil; govde tek kanonik kaynaktan turetilmelidir."
    )


def test_workflow_triggers_only_on_manual_dispatch():
    """Parali canli LLM kosusu push/PR'da ASLA tetiklenmemeli (fail-safe)."""
    body = _text(DEPLOYED)
    trigger_block = re.search(r"^on:\n((?:[ \t]+.*\n)+)", body, re.MULTILINE)
    assert trigger_block, "`on:` tetikleme blogu bulunamadi"
    triggers = trigger_block.group(1)
    assert "workflow_dispatch" in triggers, "workflow_dispatch tanimli degil"
    for forbidden in ("push:", "pull_request:", "schedule:", "repository_dispatch:"):
        assert forbidden not in triggers, f"otomatik tetikleyici yasak: {forbidden}"


def test_both_gates_exist_with_manual_run_markers():
    body = _text(DEPLOYED)
    assert re.search(r"^  live-llm-e2e:$", body, re.MULTILINE)
    assert re.search(r"^  docker-chromium-smoke:$", body, re.MULTILINE)
    assert "Gate A" in body and "Gate B" in body


def test_gate_a_is_fail_closed_on_missing_secret():
    """OPENROUTER_API_KEY tanimsizsa is bilerek dusrmeli (sessiz atlanmaz)."""
    body = _text(DEPLOYED)
    gate_a = body.split("live-llm-e2e:", 1)[1].split("docker-chromium-smoke:", 1)[0]
    assert "secrets.OPENROUTER_API_KEY" in gate_a
    assert 'if [ -z "$OPENROUTER_API_KEY" ]' in gate_a, "fail-closed secret kontrolu yok"
    assert "::error::" in gate_a, "secret eksigi ::error:: ile isaretlenmiyor"
    assert 'LIVE_LLM_E2E: "1"' in gate_a, "LIVE_LLM_E2E=1 set edilmiyor"
    assert "OPENROUTER_MAX_SPEND_USD" in gate_a, "harcama tavani yok (para guard'i eksik)"
    assert "python live_llm_gate.py" in gate_a, "gate kosucusu cagrilmıyor"


def test_gate_b_proves_real_image_and_container_chromium():
    body = _text(DEPLOYED)
    gate_b = body.split("docker-chromium-smoke:", 1)[1]
    assert "docker compose up --build" in gate_b, "gercek imaj build adimi yok"
    assert "http://127.0.0.1:8000/health" in gate_b, "/health kontrolu yok"
    assert 'id="app"' in gate_b, "UI servis kontrolu yok"
    assert '"401"' in gate_b and '"200"' in gate_b, "production auth (401→200) kontrolu yok"
    assert "smoke_test_browser.py" in gate_b, "konteyner ici Chromium smoke yok"
    assert re.search(r"down -v", gate_b), "teardown (compose down -v) yok"


def test_concurrency_prevents_parallel_paid_runs():
    body = _text(DEPLOYED)
    block = re.search(r"^concurrency:\n((?:[ \t]+.*\n)+)", body, re.MULTILINE)
    assert block, "concurrency blogu yok — iki parali kosu es zamanli baslayabilir"
    assert "group: release-gates-" in block.group(1)
    assert "cancel-in-progress: false" in block.group(1), "cancel-in-progress false olmali"
