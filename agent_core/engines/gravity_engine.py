"""GRAVITY narrative attractor engine."""

import asyncio
import re
from collections import defaultdict

import numpy as np

from agent_core.domain.pillar_models import EvidenceStatus
from agent_core.domain.pillar_wave2_models import GravityReport, GravityWell

STOPS = {"ve", "bir", "bu", "ile", "için", "çok", "the", "and", "that", "from", "olan", "daha"}


class GravityEngine:
    def __init__(self, min_word_len=4, min_recurrence=3, black_hole_pull=2, max_wells=12):
        self.min_word_len = min_word_len
        self.min_recurrence = min_recurrence
        self.black_hole_pull = black_hole_pull
        self.max_wells = max_wells

    async def analyze(self, d):
        return await asyncio.to_thread(self._sync, d)

    def _sync(self, d):
        p = d.get("target_profile") or {}
        posts = p.get("posts") or []
        meta = p.get("posts_meta") or []
        if len(posts) < 3 or len(meta) < 3:
            return GravityReport(machine_note="GRAVITY: Yetersiz gönderi veya meta veri.")
        n = min(len(posts), len(meta))
        bucket = defaultdict(list)
        likes = []
        for i in range(n):
            x = posts[i]
            t = x if isinstance(x, str) else str(x.get("text") or x.get("caption") or "")
            m = meta[i] if isinstance(meta[i], dict) else {}
            lk = float(m.get("like_count") or m.get("likes") or 0)
            likes.append(lk)
            for w in set(re.findall(rf"\b\w{{{self.min_word_len},}}\b", t.lower())) - STOPS:
                bucket[w].append(lk)
        mean = float(np.mean(likes)) or 1
        wells = []
        for word, a in bucket.items():
            if len(a) < self.min_recurrence:
                continue
            mass = len(a) / n
            pull = float(np.mean(a)) / mean
            if mass < 0.08 and pull < 1.3:
                continue
            wells.append(
                GravityWell(
                    anchor=word,
                    mass=mass,
                    density=float(np.std(a)),
                    pull=pull,
                    recurrence=len(a),
                    is_black_hole=pull >= self.black_hole_pull and mass >= 0.05,
                    observables=[f"'{word}': {len(a)} geçiş, pull=×{pull:.2f}."],
                    evidence_refs=[f"gravity:{word}:n={len(a)}"],
                )
            )
        wells.sort(key=lambda x: (-x.pull, -x.mass))
        wells = wells[: self.max_wells]
        dom = wells[0].anchor if wells else None
        return GravityReport(
            status=EvidenceStatus.OBSERVED if wells else EvidenceStatus.WEAK,
            wells=wells,
            dominant_attractor=dom,
            total_anchors_scanned=len(bucket),
            machine_note=f"GRAVITY: {len(wells)}/{len(bucket)} kuyu · dominant={dom or '—'}",
            evidence_refs=[f"gravity:total_anchors={len(bucket)}"],
        )
