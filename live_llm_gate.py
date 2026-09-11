"""
CANLI LLM RELEASE GATE (manuel — gercek OpenRouter anahtari ile).

Calistirma (yerelde):
    OPENROUTER_API_KEY=sk-or-v1-... LIVE_LLM_E2E=1 python live_llm_gate.py

GitHub Actions'ta manuel tetik:
    .github/workflows/release-gates.yml  (workflow_dispatch; secret: OPENROUTER_API_KEY)

Kapsanan yol:
    input -> mirror_truth -> passion_mapper -> ... -> resonance_synthesizer
          -> HolisticProfile

Basarı kriterleri (kullanici tanimli):
    [1] status = completed veya partially_completed
    [2] evidence_chain dolu (gercek, mock OLMAYAN cagrilar)
    [3] kritik analiz ajanlarinda sifir UNAVAILABLE fallback
        (osint/autonomous_verifier anahtarsiz UNAVAILABLE/UNVERIFIED donebilir
        — bunlar BEKLENEN davranistir, kapsam disidir)
    [4] HolisticProfile.passions/frictions/cognitive/bridge dolu ve schema-valid
    [5] Hakem modeli (OPENROUTER_JUDGE_MODEL; varsayilan openai/gpt-5.6-sol-pro)
        ciktiyi onayliyor

Cikis kodu: tum kriterler saglanirsa 0, aksi halde 1 (CI fail).
"""

import asyncio
import json
import os
import sys

# pytest testpaths=tests oldugundan bu dosya toplanmaz; yine de acik isaret.
__test__ = False

# Ana analiz zincirindeki LLM'li kritik ajanlar. Bunlardan hicbiri
# UNAVAILABLE (data_confidence=False) donmemeli.
CRITICAL_AGENTS = (
    "mirror_truth",
    "human_behavior",
    "passion_mapper",
    "friction_detector",
    "cognitive_profiler",
    "resonance_synthesizer",
    "pattern_interrupt",
)

DEFAULT_JUDGE_MODEL = "openai/gpt-5.6-sol-pro"  # "hakem / kritik gorev" (kullanici listesi #9)


def main() -> int:
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key.startswith("sk-or-v1-YOUR"):
        print("FAIL: OPENROUTER_API_KEY gerekli (placeholder kabul edilmez)")
        return 1
    if os.getenv("LIVE_LLM_E2E") != "1":
        print("FAIL: LIVE_LLM_E2E=1 gerekli")
        return 1
    return asyncio.run(_run_gate(key))


async def _run_gate(key: str) -> int:
    from agent_core.task_executor import PinealExecutor

    os.environ.setdefault("OPENROUTER_MAX_OUTPUT_TOKENS", "800")
    os.environ.setdefault(
        "OPENROUTER_AGENT_CHAIN_FRICTION_DETECTOR",
        "google/gemini-3.7-flash,deepseek/deepseek-v4-pro,anthropic/claude-sonnet-5",
    )
    executor = PinealExecutor(log_callback=lambda lvl, msg: print(f"[{lvl}] {msg}"))
    executor.llm_gateway.max_output_tokens = 800
    executor.llm_gateway.set_key(key, unlock_live=True)

    # Kisa ve gercekci girdi: token maliyetini sinirli tutar, 360 yolunun
    # tamamini (mirror_truth, human_behavior, passion_mapper, friction_detector,
    # cognitive_profiler, resonance_calc, pattern_interrupt, resonance_synthesizer) tetikler.
    payload = {
        "user_profile": {
            "bio": "Görsel araştırmacı ve mimari kompozisyon analisti. Analog dokular, minimalist mekanlar ve sessizlik üzerine çalışıyorum.",
            "posts": [
                "Sessiz detaylar her zaman en güçlü hikayeyi anlatır.",
                "Işığın ve gölgenin mekandaki ritmini inceliyorum.",
                "Gece sakinliğinde analog arşivleri taramak zihni tazeliyor.",
            ],
            "private_rituals": ["gece okumalari", "analog fotograf cekimi", "karanlik oda baskisi"],
            "late_night_playlist": ["ambient", "caz", "klasik piyano"],
            "secret_envies": ["sahici ve yalin paylasimlar", "yapmaciksiz derinlik"],
        },
        "target_profile": {
            "username": "@gate_ornek",
            "bio": "Mimar ve analog fotografci. Estetik her seydir. Sadece sahici ve yalin isler; yapmacik kalabaliklar, samimiyetsiz gurultu ve bos ovgulerden kesinlikle uzak durun.",
            "posts": [
                "Sabah isiginda cekim yaptim, sehir farkli gorunuyor.",
                "Sessizlik en duru tasarimcidir; gereksiz toplantilar ve laf kalabaligi zihni kirletir.",
                "Yeni analog sergi hazirligi basladi, sadece dogal isik ve mekan geometrisi.",
                "Yapay sohbetler ve samimiyetsiz iltifatlar enerjimi aninda tuketiyor, ozel alanima saygi bekliyorum.",
            ],
            "post_times": ["01:30", "02:45", "03:15", "14:00"],
        },
    }

    print("[gate] pipeline basliyor (kriter 1-4)...")
    result = await executor.execute_task(payload, task_id="live_gate")
    if result.status not in ("completed", "partially_completed"):
        print(f"  [gate debug] status={result.status}, reason={result.halted_reason}, completed_agents={result.completed_agents}")

    checks: list = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), str(detail)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    check(
        "status completed/partially_completed",
        result.status in ("completed", "partially_completed"),
        str(result.status),
    )
    check(
        "evidence_chain dolu",
        len(result.evidence_chain) > 0,
        f"{len(result.evidence_chain)} adim",
    )

    fallback_hits = []
    for item in result.evidence_chain:
        r = item.get("result") or {}
        if isinstance(r, dict) and r.get("data_confidence") is False:
            fallback_hits.append(f"{item.get('agent')}:{r.get('fallback_reason')}")
    critical_hits = [h for h in fallback_hits if h.split(":", 1)[0] in CRITICAL_AGENTS]
    check(
        "kritik ajanlarda sifir UNAVAILABLE fallback",
        not critical_hits,
        str(critical_hits) if critical_hits else "temiz",
    )

    hp = result.holistic_profile
    check("HolisticProfile var", hp is not None)
    check("passions dolu", bool(hp and hp.passions and hp.passions.core_passions))
    check("frictions var", bool(hp and hp.frictions is not None))
    check("cognitive var", bool(hp and hp.cognitive is not None))
    bridge = hp.bridge if hp else None
    check("bridge var", bridge is not None)
    check(
        "suggested_opening_message dolu",
        bool(bridge and (bridge.suggested_opening_message or "").strip()),
        (bridge.suggested_opening_message or "")[:120] if bridge else "",
    )

    print("[gate] kriter 5: hakem modeli degerlendirmesi...")
    judge_ok = await _judge(executor, result)
    check("hakem onayi", judge_ok)

    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n[gate] SONUC: {len(checks) - len(failed)}/{len(checks)} kriter PASS")
    if failed:
        print("[gate] BASARISIZ kriterler:", failed)
        return 1
    print("[gate] TUM KRITERLER SAGLANDI")
    return 0


async def _judge(executor, result) -> bool:
    model = os.getenv("OPENROUTER_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    hp = result.holistic_profile
    bridge = hp.bridge if hp else None
    summary = {
        "status": "completed_profile" if result.holistic_profile else str(result.status),
        "evidence_adimlari": [e.get("agent") for e in result.evidence_chain],
        "passions": (hp.passions.core_passions if hp and hp.passions else []),
        "frictions": (hp.frictions.sensitivities if hp and hp.frictions else []),
        "bridge": {
            "shared_passions": (bridge.shared_passions if bridge else []),
            "opening_message": (bridge.suggested_opening_message if bridge else ""),
        },
    }
    prompt = (
        "Sen bagimsiz bir kalite hakemisin. Asagidaki 360 profil ciktisini "
        "degerlendir: sonuc tutarli mi ve uretilen ilk temas mesaji varlik/"
        "ictenlik acisindan makul mu? Profil basariyla cikarilmis ve temas mesaji "
        "yapmaciksiz ise 'APPROVE', aksi halde 'REJECT' yaz. "
        "Yanitini kisa gerekce ve ardindan APPROVE veya REJECT olarak ver:\n\n"
        + json.dumps(summary, ensure_ascii=False)[:2000]
    )
    models_to_try = [model]
    for fb in ("openai/gpt-5.6-luna", "google/gemini-3.7-flash"):
        if fb not in models_to_try:
            models_to_try.append(fb)

    last_exc = None
    for m in models_to_try:
        try:
            raw = await executor.llm_gateway.query(
                prompt,
                temperature=0.0,
                model=m,
                system_prompt="Sen titiz bir cikti denetcisisin.",
            )
            verdict = (raw or "").strip()
            print(f"  [hakem {m}]: {verdict[:300]}")
            verdict_upper = verdict.upper()
            verdict_clean = verdict_upper.replace(".", " ").replace(":", " ").strip()
            tokens = verdict_clean.split()
            decision = None
            for tok in reversed(tokens):
                if tok in ("APPROVE", "APPROVED"):
                    decision = True
                    break
                if tok in ("REJECT", "REJECTED"):
                    decision = False
                    break
            if decision is not None:
                return decision
            return "APPROVE" in verdict_upper and "REJECT" not in verdict_upper
        except Exception as exc:
            last_exc = exc
            print(f"  [hakem uyarisi] {m} hata verdi ({exc}), siradaki model deneniyor...")
            continue

    print(f"  [FAIL] hakem cagrisi tum modellerde hata verdi: {last_exc}")
    return False


if __name__ == "__main__":
    sys.exit(main())
