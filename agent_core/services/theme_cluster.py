"""GÖREV 2.1 — Denetimsiz semantik kumeleme: profil-spesifik temalar.

Statik sozluk YOK, es-anlamli listesi YOK, LLM YOK, rastgelelik YOK.
Yontem (deterministik, saf stdlib):
  1. Her metin -> karakter 3-gram TF vektoru (kucuk harf, bosluk normalize).
  2. Ciftler arasi kosinus benzerligi; esik-ici ciftler birlestirilir
     (union-find; kok secimi index-kucuge, sira bagimsiz ve kararli).
  3. Kume = tema. K SABITI YOKTUR: tema sayisi veriden dogar (1..n).
  4. En buyuk kume payi = tekrar skoru (kompulsif tekrar olcusu);
     tekil kumeler = izole anomali.

THEME_SIM_THRESHOLD v1 sezgiselidir; davranisi testlerle kilitlidir.
Cikti JSON-serializable'dir; exemplar'lar kaynak metinden BIREBIR kesittir
(alinti uydurulmaz, en fazla 120 karakter).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List

THEME_SIM_THRESHOLD = 0.30
_NGRAM_N = 3
_EXEMPLAR_LEN = 120


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _ngrams(text: str, n: int = _NGRAM_N) -> Counter:
    norm = _normalize(text)
    if len(norm) < n:
        return Counter([norm]) if norm else Counter()
    return Counter(norm[i:i + n] for i in range(len(norm) - n + 1))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(count * b.get(gram, 0) for gram, count in a.items())
    if dot == 0:
        return 0.0
    na = math.sqrt(sum(c * c for c in a.values()))
    nb = math.sqrt(sum(c * c for c in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def cluster_texts(texts) -> Dict:
    """Metinleri profil-spesifik temalara kumeler (saf fonksiyon).

    Giris: string listesi (bio + caption'lar). Bos/bosluk/string-disi
    ogeler elenir (sayiya katilmaz, uydurma ogretmen yok).
    Cikis: method, threshold, n_texts, n_themes (K), themes
    [{id, size, members, exemplar}], repetition_score, anomaly_indices,
    isolated_anomaly_count. n == 0 ise sifir-govdeli sonuc doner (hata yok).
    """
    clean = [t for t in (texts or []) if isinstance(t, str) and t.strip()]
    n = len(clean)
    base = {
        "method": "char3gram-cosine-unionfind",
        "threshold": THEME_SIM_THRESHOLD,
        "n_texts": n,
        "n_themes": 0,
        "themes": [],
        "repetition_score": 0.0,
        "anomaly_indices": [],
        "isolated_anomaly_count": 0,
    }
    if n == 0:
        return base

    vecs = [_ngrams(t) for t in clean]
    parent = list(range(n))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: int, b: int) -> None:
        ra, rb = _find(a), _find(b)
        if ra == rb:
            return
        # Kucuk index kok olur: birlesme sirasi sonucu degistirmez.
        if rb < ra:
            ra, rb = rb, ra
        parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(vecs[i], vecs[j]) >= THEME_SIM_THRESHOLD:
                _union(i, j)

    groups: Dict[int, List[int]] = {}
    for idx in range(n):
        groups.setdefault(_find(idx), []).append(idx)

    ordered = sorted(groups.values(), key=lambda m: (-len(m), m[0]))
    themes = [
        {
            "id": tid,
            "size": len(members),
            "members": members,
            "exemplar": clean[members[0]][:_EXEMPLAR_LEN],
        }
        for tid, members in enumerate(ordered)
    ]
    anomalies = sorted(
        idx for members in ordered if len(members) == 1 for idx in members
    )
    base["n_themes"] = len(themes)
    base["themes"] = themes
    base["repetition_score"] = round(len(ordered[0]) / n, 3)
    base["anomaly_indices"] = anomalies
    base["isolated_anomaly_count"] = len(anomalies)
    return base
