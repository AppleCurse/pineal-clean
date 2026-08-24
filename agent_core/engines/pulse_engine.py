"""PULSE digital body-language metrics."""

import asyncio
import re

import numpy as np

from agent_core.domain.pillar_models import EvidenceStatus
from agent_core.domain.pillar_wave2_models import BiometricSignal, PulseReport


class PulseEngine:
    def __init__(self, min_posts=5):
        self.min_posts = min_posts

    async def analyze(self, d):
        return await asyncio.to_thread(self._sync, d)

    def _sync(self, d):
        texts = [
            x if isinstance(x, str) else str(x.get("text") or x.get("caption") or "")
            for x in (d.get("target_profile") or {}).get("posts") or []
        ]
        texts = [x for x in texts if len(x) >= 10]
        if len(texts) < self.min_posts:
            return PulseReport(machine_note=f"PULSE: {len(texts)} metin < min {self.min_posts}.")
        lens = np.array([len(x) for x in texts], float)
        vol = float(lens.std() / max(lens.mean(), 1))
        p = float(np.mean([(x.count("!") + x.count("?")) / len(x) for x in texts]))
        emo = float(np.mean([len(re.findall("[😀-🙏]", x)) for x in texts]))
        caps = float(np.mean([sum(c.isupper() for c in x) / max(1, sum(c.isalpha() for c in x)) for x in texts]))
        q = float(np.mean([x.count("?") / max(1, len(x.split())) for x in texts]))
        vals = [
            ("length_volatility", "Metin Uzunluk Volatilitesi", vol, 0.5, 0.2),
            ("punctuation_intensity", "Noktalama Yoğunluğu", p, 0.04, 0.02),
            ("emoji_diversity", "Emoji Yoğunluğu", emo, 1.2, 0.8),
            ("caps_aggression", "Büyük Harf Oranı", caps, 0.06, 0.03),
            ("question_ratio", "Soru Oranı", q, 0.04, 0.02),
        ]
        s = [
            BiometricSignal(
                signal_type=a,
                label=b,
                value=v,
                z_score=(v - base) / sd,
                baseline=base,
                interpretation="Tanısal olmayan davranışsal ölçüm.",
            )
            for a, b, v, base, sd in vals
        ]
        rh = "erratic" if vol > 0.85 else "variable" if vol > 0.55 else "steady" if vol > 0.3 else "mechanical"
        return PulseReport(
            status=EvidenceStatus.OBSERVED,
            signals=s,
            baseline_volatility=vol,
            rhythm_signature=rh,
            machine_note=f"PULSE: 5 sinyal · vol={vol:.3f} · rhythm={rh}",
            evidence_refs=[f"pulse:corpus_size={len(texts)}"],
        )
