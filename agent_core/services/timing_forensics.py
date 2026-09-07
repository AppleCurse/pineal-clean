"""Zaman forensigi: legacy dagilim olcumleri + GÖREV 2.2 yorunge motoru.

Legacy (night_share/peak_hour/median_drift/histogram/machine_note) ARITMETIK
OLCUMDUR; asagidaki tuketiciler (executor logu, pattern_interrupt, panel)
tarafindan okunur ve birebir korunur. GÖREV 2.2 "trajectory" anahtariyla
EK yapi katar: S(t) durum dizisi, entropi/varyans kirilmalari, rejimler.
Duygusal etiket YOKTUR: motor yapi uretir, yorumu analist yapar.
"""

from datetime import datetime, timezone
from statistics import pvariance
from typing import Dict, List, Optional
import math
import re

# GÖREV 2.2 v1 sezgisel esikler (davranis testlerle kilitlidir).
ENTROPY_JUMP_THRESHOLD = 0.5   # |ΔH| (nat) uzeri = entropi sictamasi
VARIANCE_SHIFT_RATIO = 3.0     # varyans orani uzeri = varyans makasi
_VAR_FLOOR = 0.01              # sifira-bolum kilidi (saat^2)


def _extract_hour(t: str) -> Optional[int]:
    m = re.search(r"(?:T|^|\s)([01]?\d|2[0-3]):([0-5]\d)", str(t))
    if m:
        return int(m.group(1))
    m2 = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", str(t))
    return int(m2.group(1)) if m2 else None


def _extract_dt(t) -> Optional[datetime]:
    """ISO-8601 -> datetime. Naive girdi UTC sayilir (girdi sozlesmesi:
    aware ISO; karisik cerceveli girdi siralama hatasi uretebilir)."""
    if not isinstance(t, str) or not t.strip():
        return None
    try:
        parsed = datetime.fromisoformat(t.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _entropy(probs: List[float]) -> float:
    return round(-sum(p * math.log(p) for p in probs if p > 0.0), 3)


def _daypart(hour: int) -> str:
    if hour >= 23 or hour < 5:
        return "night"
    if hour < 9:
        return "morning"
    if hour < 18:
        return "workday"
    return "evening"


def analyze_trajectory(
    post_times: List[str],
    engagement: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """GÖREV 2.2: S(t) durum fonksiyonu + kirilma/tekil nokta tespiti.

    - Ornekler zamana gore siralanir (t_0 -> t_N); her durum {t, gap, saat}.
    - Seri ortadan ikiye bolunur: gun-bolumu entropisi + aralik varyansi
      iki yarida karsilastirilir (legacy drift ile ayni yari-mantik).
    - En az 3 tarihli ornek gerekir (legacy ile ayni durustluk tabani);
      ruptur aramasi icin n >= 4 (her yari en az 2 ornek).
    - engagement (varsa): posts_meta ile AYNI sirada sayim sozlukleri;
      siralama sonrasi index'ten yeniden hizalanir, hizalama disi
      sayim ASLA odunc alinmaz.
    """
    pairs = [(i, dt) for i, dt in
             ((_i, _extract_dt(t)) for _i, t in enumerate(post_times or []))
             if dt is not None]
    if len(pairs) < 3:
        return None
    pairs.sort(key=lambda p: (p[1], p[0]))

    eng = list(engagement or [])

    def _likes_of(order_pos: int) -> Optional[float]:
        orig_idx = pairs[order_pos][0]
        if orig_idx >= len(eng):
            return None
        entry = eng[orig_idx]
        if not isinstance(entry, dict):
            return None
        val = entry.get("like_count")
        return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None

    states = []
    prev = None
    for order_pos, (_orig, dt) in enumerate(pairs):
        gap = None if prev is None else round((dt - prev).total_seconds() / 3600.0, 3)
        states.append({
            "idx": order_pos,
            "t": dt.isoformat(),
            "gap_hours": gap,
            "hour": dt.hour,
        })
        prev = dt

    n = len(states)
    split = n // 2
    first, second = states[:split], states[split:]

    def _half_entropy(half: List[Dict]) -> float:
        counts: Dict[str, int] = {}
        for s in half:
            part = _daypart(s["hour"])
            counts[part] = counts.get(part, 0) + 1
        total = len(half)
        return _entropy([c / total for c in counts.values()])

    def _half_var(half: List[Dict]) -> float:
        gaps = [s["gap_hours"] for s in half if s["gap_hours"] is not None]
        if len(gaps) < 2:
            return 0.0
        return round(pvariance(gaps), 3)

    h1, h2 = _half_entropy(first), _half_entropy(second)
    v1, v2 = _half_var(first), _half_var(second)
    entropy_jump = round(abs(h2 - h1), 3)
    floored = (max(v1, _VAR_FLOOR), max(v2, _VAR_FLOOR))
    var_ratio = round(max(floored) / min(floored), 3)

    ruptures = []
    if n >= 4:
        pivot = second[0]
        if entropy_jump > ENTROPY_JUMP_THRESHOLD:
            ruptures.append({
                "kind": "entropy_jump",
                "at_idx": pivot["idx"],
                "at_t": pivot["t"],
                "magnitude": entropy_jump,
            })
        if var_ratio > VARIANCE_SHIFT_RATIO:
            ruptures.append({
                "kind": "variance_shift",
                "at_idx": pivot["idx"],
                "at_t": pivot["t"],
                "magnitude": var_ratio,
            })

    def _regime(half: List[Dict]) -> Dict:
        counts: Dict[str, int] = {}
        for s in half:
            part = _daypart(s["hour"])
            counts[part] = counts.get(part, 0) + 1
        gaps = [s["gap_hours"] for s in half if s["gap_hours"] is not None]
        return {
            "from_idx": half[0]["idx"],
            "to_idx": half[-1]["idx"],
            "from_t": half[0]["t"],
            "to_t": half[-1]["t"],
            "n": len(half),
            "dominant_daypart": max(counts, key=counts.get),
            "mean_gap_hours": round(sum(gaps) / len(gaps), 3) if gaps else None,
        }

    like_means = []
    for half in (first, second):
        vals = [_likes_of(s["idx"]) for s in half]
        vals = [v for v in vals if v is not None]
        like_means.append(round(sum(vals) / len(vals), 2) if vals else None)
    like_shift = None
    if like_means[0] and like_means[1]:
        like_shift = round(max(like_means) / min(like_means), 3)

    span_hours = round((pairs[-1][1] - pairs[0][1]).total_seconds() / 3600.0, 2)
    return {
        "method": "state-trajectory-halves-v1",
        "n": n,
        "t_0": pairs[0][1].isoformat(),
        "t_N": pairs[-1][1].isoformat(),
        "span_hours": span_hours,
        "states": states,
        "entropy_first": h1,
        "entropy_second": h2,
        "entropy_jump": entropy_jump,
        "var_first": v1,
        "var_second": v2,
        "var_ratio": var_ratio,
        "ruptures": ruptures,
        "regimes": [_regime(first), _regime(second)],
        "engagement": {
            "like_mean_first": like_means[0],
            "like_mean_second": like_means[1],
            "like_shift_ratio": like_shift,
        },
        "note": "n<4: ruptur aranmadi (yari basina en az 2 ornek gerekir)"
                if n < 4 else "ok",
    }


def analyze_timing(post_times: List[str], engagement: Optional[List[Dict]] = None) -> Optional[Dict]:
    hours = [h for h in (_extract_hour(t) for t in (post_times or [])) if h is not None]
    if len(hours) < 3:
        return None
    hist = {f"{h:02d}": 0 for h in range(24)}
    for h in hours:
        hist[f"{h:02d}"] += 1
    night = sum(1 for h in hours if h >= 23 or h < 5)   # 23:00-04:59
    evening = sum(1 for h in hours if 20 <= h < 23)
    workday = sum(1 for h in hours if 9 <= h < 18)

    def _median(xs):
        xs = sorted(xs)
        n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    first_half, second_half = hours[: len(hours) // 2], hours[len(hours) // 2:]
    drift_hours = (_median(second_half) - _median(first_half)) if first_half and second_half else 0
    if drift_hours > 12:
        drift_hours -= 24
    if drift_hours < -12:
        drift_hours += 24
    peak = max(hist, key=hist.get)
    return {
        "samples": len(hours),
        "night_share": round(night / len(hours), 3),
        "evening_share": round(evening / len(hours), 3),
        "workday_share": round(workday / len(hours), 3),
        "peak_hour": f"{peak}:00",
        "median_drift_hours": round(drift_hours, 1),
        "histogram": {k: v for k, v in hist.items() if v},
        "machine_note": (
            f"{len(hours)} paylaşımdan %{round(night/len(hours)*100)} gece (23:00-05:00) saati, "
            f"tepe saat {peak}:00, zaman içinde medyan kayma {drift_hours:+.1f} saat. "
            f"(Bu cümle tamamen aritmetikten üretilmiştir; LLM değildir.)"
        ),
        # GÖREV 2.2: yorunge blogu (legacy anahtarlar birebir korunur).
        "trajectory": analyze_trajectory(post_times, engagement=engagement),
    }
