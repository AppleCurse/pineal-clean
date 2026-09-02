#!/usr/bin/env python3
"""Nous hesap kataloğu doğrulayıcı — "hangi rota free?" sorusunu HESAPTAN çözer.

Neden var: 2026-09-02 routing tartışmasında free/paid slug iddiaları statik
listelerle çekişti. Kullanıcının Nous aboneliği mevcut; nihaî kanıt betiklerin
değil, hesabın kendi `/models` yanıtıdır. Bu betik şunu yapar:

    GET $NOUS_API_BASE/models          (Authorization: Bearer $NOUS_API_KEY)
      -> her model: fiyat (per-1M) + bağlam + VAR/YOK etiketi
      -> pricing==0 olanlar FREE ROTA olarak listelenir
      -> beklenen tohum rotalar (SEED_ROUTES) tek tek işaretlenir

Kurallar:
  - Anahtar yalnız env'den okunur, asla basılmaz/saklanmaz.
  - Ağ çıktısı diske yazılmaz; yalnız stdout.
  - Katalog okunamazsa exit 2 (fail-closed, kısmi çıktıyla karar yürütülmez).

Kullanım:
    export NOUS_API_KEY=...            # zorunlu
    export NOUS_API_BASE=https://inference-api.nousresearch.com/v1   # isteğe bağlı
    python3 scripts/verify_nous_catalog.py            # insan okur
    python3 scripts/verify_nous_catalog.py --json     # makine okur
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://inference-api.nousresearch.com/v1"

# Kullanıcının panelinde gördüğünü bildirdiği rotalar (2026-09-02).
# Burada "beklenen" olmaları "doğru oldukları" anlamına gelmez — betiğin tek işi
# hesap kataloğunda VAR/YOK damgalamaktır; katalog cevabı tartışmayı bitirir.
SEED_ROUTES = [
    "stepfun/step-3.7-flash:free",
    "upstage/solar-pro4:free",
    "meituan/longcat-2.0:free",
    "poolside/laguna:free",
]

# Paid omurga (hesapta olması beklenen iki ücretli rota). Bunlardan biri
# katalogda yoksa exit 1 — bu ikisi FINAL matrisinin paid kanadı.
PAID_SPINE = [
    "openai/gpt-5.6-luna",
    "anthropic/claude-sonnet-5",
]


def _per_million(raw) -> str:
    try:
        return f"${float(raw) * 1_000_000:.4g}"
    except (TypeError, ValueError):
        return "?"


def _is_zero_price(pricing) -> bool:
    """Açık sıfır kanıtı. Alan eksik/okunamazsa False (fail-closed)."""
    if not isinstance(pricing, dict):
        return False
    try:
        return float(pricing.get("prompt")) == 0.0 and float(pricing.get("completion")) == 0.0
    except (TypeError, ValueError):
        return False


def main() -> int:
    base = os.getenv("NOUS_API_BASE", DEFAULT_BASE).rstrip("/")
    key = os.getenv("NOUS_API_KEY", "").strip()
    as_json = "--json" in sys.argv

    if not key:
        print("HATA: NOUS_API_KEY env'i boş. `export NOUS_API_KEY=...` ile verin.", file=sys.stderr)
        return 2

    req = urllib.request.Request(
        f"{base}/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"HATA: katalog HTTP {exc.code} (auth/endpoint kontrol edin)", file=sys.stderr)
        return 2
    except Exception as exc:  # ağ/copy hatası -> fail-closed
        print(f"HATA: katalog okunamadı: {exc}", file=sys.stderr)
        return 2

    rows = payload.get("data")
    if not isinstance(rows, list):
        print("HATA: beklenmedik katalog şeması (data listesi yok)", file=sys.stderr)
        return 2

    by_id = {m.get("id"): m for m in rows if isinstance(m, dict) and m.get("id")}

    def summarize(model_id: str):
        m = by_id.get(model_id)
        if not m:
            return {"present": False}
        pricing = m.get("pricing") or {}
        return {
            "present": True,
            "free": _is_zero_price(pricing),
            "in_per_1m": _per_million(pricing.get("prompt")),
            "out_per_1m": _per_million(pricing.get("completion")),
            "context": m.get("context_length") or (m.get("top_provider") or {}).get("context_length"),
        }

    report = {
        "base": base,
        "catalog_size": len(by_id),
        "paid_spine": {s: summarize(s) for s in PAID_SPINE},
        "seed_routes": {s: summarize(s) for s in SEED_ROUTES},
        "free_roster": [
            {"id": mid, "context": (m.get("context_length") or (m.get("top_provider") or {}).get("context_length"))}
            for mid, m in sorted(by_id.items())
            if _is_zero_price(m.get("pricing"))
        ],
        "all_models": sorted(by_id.keys()),
    }

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Nous katalog: {report['catalog_size']} model ({base})\n")
        print("== Paid omurga ==")
        for s, r in report["paid_spine"].items():
            print(f"  {'✅' if r['present'] else '❌ YOK'} {s}"
                  + (f"  in={r.get('in_per_1m')} out={r.get('out_per_1m')} ctx={r.get('context')}" if r["present"] else ""))
        print("\n== Tohum free rotalar ==")
        for s, r in report["seed_routes"].items():
            tag = "✅ FREE" if r["present"] and r["free"] else ("⚠️ VAR ama pricing!=0" if r["present"] else "❌ YOK")
            print(f"  {tag} {s}" + (f"  ctx={r.get('context')}" if r["present"] else ""))
        print(f"\n== Hesaptaki tüm FREE rotalar ({len(report['free_roster'])}) ==")
        for item in report["free_roster"]:
            print(f"  {item['id']}  ctx={item['context']}")

    missing_spine = [s for s, r in report["paid_spine"].items() if not r["present"]]
    return 1 if missing_spine else 0


if __name__ == "__main__":
    sys.exit(main())
