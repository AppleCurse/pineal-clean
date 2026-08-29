import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Any

def _normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[\s\u00a0]+", " ", t)
    t = re.sub(r"[^\w\sçığöşüÇİĞÖŞÜ%.,:;@#()\-/'\"+]", "", t)
    return t.strip()

def _source_corpus(source_texts: List[str]) -> List[str]:
    return [_normalize(s) for s in source_texts if s and str(s).strip()]

def quote_matches(quote: str, corpus: List[str], threshold: float = 0.70) -> bool:
    """Alıntı kaynak korpustaki herhangi bir metin parçasıyla eşleşiyor mu?"""
    q = _normalize(quote)
    if len(q) < 4:
        return False
    for src in corpus:
        if len(src) < 4:
            continue
        if q in src:
            return True
        if len(src) <= len(q) * 3:
            if SequenceMatcher(None, q, src).ratio() >= threshold:
                return True
        else:
            step = max(1, len(q) // 2)
            for i in range(0, len(src) - len(q) + 1, step):
                window = src[i:i + len(q) * 2]
                if SequenceMatcher(None, q, window).ratio() >= threshold:
                    return True
    return False

def guard_report(report: Dict[str, Any], input_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """DepthReport sözlüğünü alıntı-bazlı temizler."""
    tp = (input_data.get("target_profile") or {})
    visual = input_data.get("visual_evidence") or {}
    audit = input_data.get("follower_audit") or {}
    timing = input_data.get("timing_forensics") or {}
    
    source_texts: List[str] = [str(tp.get("bio", ""))]
    source_texts += [str(p) for p in (tp.get("posts") or [])]
    source_texts += [str(t) for t in (tp.get("post_times") or [])]
    source_texts += [str(tp.get("username", ""))]
    if tp.get("followers"):
        source_texts.append(f"followers {tp.get('followers')}")
    if tp.get("following"):
        source_texts.append(f"following {tp.get('following')}")
    if tp.get("post_count"):
        source_texts.append(f"post_count {tp.get('post_count')}")
        
    for key in ("detected_objects", "environment_and_places", "activity_signals"):
        source_texts += [str(x) for x in (visual.get(key) or [])]
    if visual.get("aesthetic_style"):
        source_texts.append(str(visual["aesthetic_style"]))
    if visual.get("visual_evidence_summary"):
        source_texts.append(str(visual["visual_evidence_summary"]))
        
    source_texts += [str(e) for e in (audit.get("evidence") or [])]
    if audit.get("verdict"):
        source_texts.append(f"{audit.get('verdict')} engagement_rate {audit.get('engagement_rate', '')}")
    if timing.get("machine_note"):
        source_texts.append(str(timing.get("machine_note")))

    # [FAZ 4] Public-web kaynak metinleri (crawl4ai zenginleştirmesinden
    # available=True iken çağıranın koyduğu gerçek sayfa metinleri). Alan
    # yoksa korpus BİREBİR aynı kalır — mevcut guard davranışı değişmez.
    for src in (input_data.get("public_web_sources") or []):
        text = src.get("text") if isinstance(src, dict) else None
        if isinstance(text, str) and text.strip():
            source_texts.append(text[:20000])

    corpus = _source_corpus(source_texts)
    stats = {
        "checked": 0,
        "dropped_no_quote": 0,
        "dropped_fake_quote": 0,
        "dropped_topics": [],
        "kept": 0
    }

    def clean(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for f in findings or []:
            stats["checked"] += 1
            quotes = (f or {}).get("evidence_quotes") or []
            if not quotes:
                stats["dropped_no_quote"] += 1
                stats["dropped_topics"].append((f or {}).get("topic", "?"))
                continue
            real = [q for q in quotes if quote_matches(q, corpus)]
            if not real:
                stats["dropped_fake_quote"] += 1
                stats["dropped_topics"].append((f or {}).get("topic", "?"))
                continue
            f["evidence_quotes"] = real
            out.append(f)
            stats["kept"] += 1
        return out

    if isinstance(report.get("reality_findings"), list):
        report["reality_findings"] = clean(report.get("reality_findings"))
    if isinstance(report.get("contradictions"), list):
        report["contradictions"] = clean(report.get("contradictions"))

    rationale = report.get("reality_rationale") or ""
    if rationale and not any(quote_matches(q, corpus) for q in re.findall(r'"([^"]{6,})"', rationale)):
        report["reality_rationale"] = rationale + " [not: gerekçede kaynak-alıntı doğrulanamadı]"
        stats["rationale_unverified"] = True

    report["quote_guard"] = stats
    return report, stats
