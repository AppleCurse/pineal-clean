"""Epistemik sözleşme — Pineal pipeline'ının tek doğruluk standardı.

Her ajan çıktısı dört statüden birini taşır ve downstream tüketici bunu ZORUNLU
okur. Amaç: bir LLM yorumu hiçbir noktada etiketsiz olarak "ölçülmüş kanıt"a
dönüşemesin (FORENSIC_ENGINE_ROADMAP_2026-09-02.md, Faz 1).

Kurallar:
1. Statüyü KOD yazar, model ÖNEREMEZ. LLM şemasına epistemic alanı konmaz;
   damgayı executor/storage katmanı basar (ör. `_store_authentic_vector`).
2. Varsayılan asla OBSERVED/VERIFIED değildir — bilinmeyen kaynak INTERPRETED
   olarak doğar; kanıt zinciri olmadan VERIFIED'a terfi edilemez.
3. Tüketici (rezonans, bellek ortalaması, karar motoru) statüyü görmezden
   gelirse bu bir hata sayılır ve testle mühürlenir.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EpistemicStatus(str, Enum):
    """Bir bulgunun kaynağa bağlanma gücü. Sıralama tek yönlü, terfi kanıtla."""

    UNAVAILABLE = "unavailable"      # veri yok / kaynak çöktü — ağırlık 0
    HYPOTHESIS = "hypothesis"        # model iddiası, kaynak bağlanmamış
    INTERPRETED = "interpreted"      # gerçek kanıt üstünde MODEL yorumu
    OBSERVED = "observed"            # kodun doğrudan ölçtüğü (deterministik)
    VERIFIED = "verified"            # bağımsız kanıtla teyit edilmiş


# Bellek/karar katmanında kullanılan agregasyon ağırlıkları.
# Etiketsiz (legacy) girdiler geçmiş davranışı bozmamak için 1.0 alır —
# yeni contract basınca legacy yol daralır.
EPISTEMIC_CONFIDENCE_WEIGHTS = {
    EpistemicStatus.OBSERVED: 1.0,
    EpistemicStatus.VERIFIED: 1.0,
    EpistemicStatus.INTERPRETED: 0.6,
    EpistemicStatus.HYPOTHESIS: 0.35,
    EpistemicStatus.UNAVAILABLE: 0.0,
}

# Vektör/dict damgalarında görülen "tahmin" işaretlerinin tek kaydı.
ESTIMATE_MARKERS = frozenset({"model_estimate", "llm_estimate", "estimated"})
# Ölçülmüş/deterministik işaretleri.
MEASURED_MARKERS = frozenset({"measured", "observed", "deterministic"})


class EpistemicResult(BaseModel):
    """Ajan çıktı modellerinin miras alacağı sözleşme mixin'i.

    Varsayılan INTERPRETED'tır — bir model `.model_construct()` ile bile
    kendini OBSERVED/VERIFIED ilan edemez değil, ama contract yükümlülüğü
    damgayı BASACAĞIN yerin kod olduğudur (test: varsayılan OBSERVED değil).
    """

    model_config = ConfigDict(extra="forbid")

    epistemic: EpistemicStatus = Field(
        default=EpistemicStatus.INTERPRETED,
        description="Kanıt statüsü — kod tarafından damgalanır, model önerisi değildir.",
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="Bu çıktının dayandığı evidence_chain girdilerine işaretler.",
    )


def read_marker(payload: Any) -> Optional[str]:
    """dict/obje içinden ham epistemik işareti oku (`_epistemic` veya `epistemic`).

    Damga yoksa None döner — 'None' 'temiz' DEMEK DEĞİLDİR, 'etiketsiz' demektir.
    """
    if isinstance(payload, dict):
        marker = payload.get("_epistemic", payload.get("epistemic"))
    else:
        marker = getattr(payload, "_epistemic", None) or getattr(payload, "epistemic", None)
    return marker if isinstance(marker, str) and marker else None


def is_estimate(payload: Any) -> bool:
    """Payload LLM tahmini olarak damgalı mı?"""
    return read_marker(payload) in ESTIMATE_MARKERS


def status_weight(payload: Any) -> float:
    """Agregasyon ağırlığı. Etiketsiz (legacy) payload 1.0 (geçmiş davranış korunur);
    tanınan statü kendi ağırlığını alır; tanınmayan string damga HYPOTHESIS sayılır."""
    marker = read_marker(payload)
    if marker is None:
        return 1.0
    if marker in MEASURED_MARKERS:
        return 1.0
    if marker in ESTIMATE_MARKERS:
        return EPISTEMIC_CONFIDENCE_WEIGHTS[EpistemicStatus.INTERPRETED]
    try:
        return EPISTEMIC_CONFIDENCE_WEIGHTS[EpistemicStatus(marker)]
    except ValueError:
        return EPISTEMIC_CONFIDENCE_WEIGHTS[EpistemicStatus.HYPOTHESIS]
