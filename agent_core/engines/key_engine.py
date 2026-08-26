"""KEY transparent rule-based synthesis."""

import asyncio

from agent_core.domain.pillar_models import EvidenceStatus
from agent_core.domain.pillar_wave2_models import KeyReport, ResonanceVector


class KeyEngine:
    async def analyze(self, freq, seismos, void, strata, gravity, pulse):
        return await asyncio.to_thread(self._sync, freq, seismos, void, strata, gravity, pulse)

    def _sync(self, freq, seismos, void, strata, gravity, pulse):
        reports = [freq, seismos, void, strata, gravity, pulse]
        if all(x.status == EvidenceStatus.INSUFFICIENT_DATA for x in reports):
            return KeyReport(machine_note="KEY: Tüm motorlar yetersiz veri döndü — sentez yapılamadı.")
        fs = (
            "Frekans verisi yetersiz."
            if freq.status == EvidenceStatus.INSUFFICIENT_DATA
            else (
                "Gece ağırlıklı"
                if freq.night_energy_share > 0.35
                else "Gündüz ağırlıklı"
                if freq.night_energy_share < 0.1
                else "Karma zaman dağılımı"
            )
        )
        tension = (
            " ↔ ".join(
                ([f"Az ifade edilen alan: {void.top_voids[0]}"] if void.top_voids else [])
                + ([f"Geçmiş tema: {strata.fossils[0].topic}"] if strata.fossils else [])
            )
            or "Belirgin bir çekirdek gerilim tespit edilemedi."
        )
        dom = gravity.dominant_attractor
        gate = (
            f"'{dom}' teması üzerinden doğal, kısa ve dengeli bir sohbet açın."
            if dom
            else "Genel gözleme dayalı doğal ve düşük baskılı yaklaşım."
        )
        walls = [f"Geçmişte kalan '{x.topic}' konusuna doğrudan yüklenmeyin." for x in strata.fossils[:2]] or [
            "Belirgin sınır tespit edilemedi; dikkatli gözlem sürdürülmeli."
        ]
        vectors = []
        if dom:
            vectors.append(
                ResonanceVector(
                    dimension="approach",
                    approach=f"'{dom}' üzerinden açık uçlu sohbet.",
                    avoid="Varsayım ve baskıdan kaçının.",
                    confidence=min(1, gravity.wells[0].pull / 3),
                    source_pillars=["gravity"],
                )
            )
        if pulse.rhythm_signature:
            # Sabit 0.6 kaldırıldı: güven, pulse motorunun kendi gerçek
            # durumundan türetilir (OBSERVED=1.0, WEAK=0.5, aksi=0.0).
            pulse_conf = (
                1.0 if pulse.status == EvidenceStatus.OBSERVED
                else 0.5 if pulse.status == EvidenceStatus.WEAK
                else 0.0
            )
            vectors.append(
                ResonanceVector(
                    dimension="rhythm_match",
                    approach=f"{pulse.rhythm_signature} ritme uyumlu iletişim.",
                    avoid="Karşı tarafın hızını zorlamayın.",
                    confidence=pulse_conf,
                    source_pillars=["pulse"],
                )
            )
        active = sum(x.status in (EvidenceStatus.OBSERVED, EvidenceStatus.WEAK) for x in reports)
        conf = active / 6
        summary = {
            k: x.machine_note or x.status.value
            for k, x in zip(["frequency", "seismos", "void", "strata", "gravity", "pulse"], reports)
        }
        return KeyReport(
            status=EvidenceStatus.OBSERVED if conf >= 0.5 else EvidenceStatus.WEAK,
            frequency_signature=fs,
            core_tension=tension,
            gate_key=gate,
            walls=walls,
            rhythm_note=f"Ritim: {pulse.rhythm_signature or 'unknown'} (vol={pulse.baseline_volatility:.3f})",
            channel_recommendation="Gönderi üzerine doğal yorum; karşılıklı ilgi oluşursa özel mesaja geçiş.",
            timing_window="Akşam/gece saatleri." if freq.night_energy_share > 0.35 else "Gündüz saatleri.",
            vectors=vectors,
            pillar_summary=summary,
            confidence=conf,
            machine_note=f"KEY: Sentez tamamlandı · güven={conf:.2f} · {active}/6 motor aktif.",
            evidence_refs=["key:synthesized"],
        )
