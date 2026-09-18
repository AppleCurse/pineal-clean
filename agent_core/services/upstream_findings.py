"""[FIX #3] Upstream findings enjeksiyon bloğu — TEK kaynak.

Sağır odalar: ajanlar birbirinin çıkarımını okuyamıyordu. Executor, her
başarılı ajan tamamlamasından deterministik bir "kanıt çekirdeği" üretip
``input_data["_upstream_findings"]`` listesine yazar (bütçe:
task_executor.UPSTREAM_FINDINGS_BUDGET_CHARS). Bu modül o listeyi LLM
ajanlarının prompt'una girecek metin bloğuna çevirir; liste yoksa/boşsa
BOŞ DİZİ döner (davranış birebir eskiyle aynı — geriye uyum).

Epistemik etiket zorunludur: çekirdekler DOĞRULANMAMIS çıkarımlardır;
tüketici ajanın kendi kanıtı çelişirse kendi kanıtı geçerlidir.
"""
from __future__ import annotations

from typing import Any


def upstream_findings_block(payload: Any) -> str:
    """payload['_upstream_findings'] listesini prompt bloğuna çevirir."""
    findings = payload.get("_upstream_findings") if isinstance(payload, dict) else None
    if not isinstance(findings, list) or not findings:
        return ""
    lines = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        agent = str(f.get("agent", "?"))[:40]
        core = str(f.get("core", "")).strip()
        if core:
            lines.append(f"- [{agent}] {core}")
    if not lines:
        return ""
    return (
        "DİĞER AJANLARIN BULGULARI (doğrulanmamış çıkarımlar — kendi "
        "kanıtınla çelişirse KENDİ KANITIN geçerlidir; bunu kopya olarak "
        "değil çapraz kontrol referansı olarak kullan):\n" + "\n".join(lines)
    )
