"""SEISMOS behavioral fracture detector."""

import asyncio
import re
import uuid

import numpy as np

from agent_core.domain.pillar_models import EvidenceStatus, SeismicEvent, SeismicKind, SeismosReport

from .frequency_engine import extract_post_series

POS = {"harika", "mutlu", "güzel", "iyi", "süper", "happy", "great", "teşekkürler"}
NEG = {"yorgun", "bitkin", "stres", "kötü", "üzgün", "sad", "bıktım"}


def polarity(t):
    w = re.findall(r"[^\W\d_]+", t.lower())
    p = sum(x in POS for x in w)
    n = sum(x in NEG for x in w)
    return (p - n) / max(1, p + n)


class SeismosEngine:
    def __init__(
        self,
        min_posts=5,
        silence_factor=4,
        min_silence_hours=72,
        tone_delta_threshold=0.55,
    ):
        self.min_posts = min_posts
        self.silence_factor = silence_factor
        self.min_silence_hours = min_silence_hours
        self.tone_delta_threshold = tone_delta_threshold

    async def analyze(self, d):
        return await asyncio.to_thread(self._sync, d)

    def _sync(self, d):
        s = extract_post_series(d)
        if len(s) < self.min_posts:
            return SeismosReport(machine_note=f"SEISMOS: {len(s)} gönderi < min {self.min_posts}.")
        gaps = np.diff([x[0].timestamp() for x in s]) / 3600
        med = float(np.median(gaps)) if len(gaps) else 0
        events = []
        for i, g in enumerate(gaps):
            if g >= max(self.min_silence_hours, self.silence_factor * max(med, 1)):
                a, b = s[i][0], s[i + 1][0]
                r = g / max(med, 1)
                events.append(
                    SeismicEvent(
                        event_id="sez_" + uuid.uuid4().hex[:12],
                        kind=SeismicKind.SILENCE_GAP,
                        intensity=float(np.clip(1 + 9 * (1 - np.exp(-r / 4)), 1, 10)),
                        timestamp=a + (b - a) / 2,
                        window_start=a,
                        window_end=b,
                        observables=[f"{g:.1f} saatlik boşluk (medyan {med:.1f}h)."],
                        metrics={"gap_hours": float(g), "ratio": float(r)},
                        hypotheses=[
                            "Planlı paylaşım duraksatması olabilir.",
                            "Seyahat, yoğunluk veya kısmi veri olabilir.",
                        ],
                        evidence_refs=[f"post:{a.isoformat()}", f"post:{b.isoformat()}"],
                    )
                )
        scores = np.array([polarity(x[1]) for x in s])
        w = 3
        for i in range(len(scores) - 2 * w + 1):
            a = float(scores[i : i + w].mean())
            b = float(scores[i + w : i + 2 * w].mean())
            delta = b - a
            if abs(delta) >= self.tone_delta_threshold:
                events.append(
                    SeismicEvent(
                        event_id="sez_" + uuid.uuid4().hex[:12],
                        kind=SeismicKind.TONE_SHIFT,
                        intensity=float(
                            np.clip(1 + 9 * (1 - np.exp(-(abs(delta) / self.tone_delta_threshold) / 4)), 1, 10)
                        ),
                        timestamp=s[i + w][0],
                        window_start=s[i][0],
                        window_end=s[i + 2 * w - 1][0],
                        observables=[f"Polarite kayması Δ={delta:+.2f}."],
                        metrics={"before": a, "after": b, "delta": delta},
                        hypotheses=["Konu değişimi veya küçük örneklem etkisi olabilir."],
                        status=EvidenceStatus.WEAK,
                        evidence_refs=[f"post:{s[i + w][0].isoformat()}"],
                    )
                )
        events.sort(key=lambda e: -e.intensity)
        mx = max((e.intensity for e in events), default=0)
        return SeismosReport(
            status=EvidenceStatus.OBSERVED if events else EvidenceStatus.WEAK,
            events=events,
            max_intensity=mx,
            event_count=len(events),
            baseline_inter_post_hours=med or None,
            machine_note=f"SEISMOS: {len(events)} olay · max={mx:.1f}",
            evidence_refs=[r for e in events for r in e.evidence_refs][:64],
        )
