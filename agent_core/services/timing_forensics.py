from typing import Dict, List, Optional
import re

def _extract_hour(t: str) -> Optional[int]:
    m = re.search(r"(?:T|^|\s)([01]?\d|2[0-3]):([0-5]\d)", str(t))
    if m:
        return int(m.group(1))
    m2 = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", str(t))
    return int(m2.group(1)) if m2 else None

def analyze_timing(post_times: List[str]) -> Optional[Dict]:
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
    }
