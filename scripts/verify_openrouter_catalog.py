#!/usr/bin/env python3
"""OpenRouter canlı katalog doğrulayıcı — slug iddialarını kaynağında çözer.

Neden var: 2026-09-02 routing taslakları tekrar tekrar "bu slug live mı?"
sorusunda bölündü (solar-pro4:free, longcat-2.0:free, gpt-5.6-sol-pro, ...).
Bu betik `GET /api/v1/models` ile canlı kataloğu çeker ve her aday slug için
VAR/YOK + fiyat + bağlam basar. Anahtar GEREKMEZ (katalog ucu herkese açık).

Kullanım:
    python3 scripts/verify_openrouter_catalog.py            # insan okur
    python3 scripts/verify_openrouter_catalog.py --json     # makine okur

Depoya anahtar/gizli değer yazmaz; ağ çıktısını diske kaydetmez.
Sadece okur ve stdout'a basar. Çıkış kodu: kritik slug (repo zincirlerinde
kullanılanlar) kayıpsa 1, aksi halde 0 — CI'a bağlanabilir.
"""
from __future__ import annotations

import json
import sys
import urllib.request

CATALOG_URL = "https://openrouter.ai/api/v1/models"

# (slug, nereden geldi) — iddia sahibi etiketi, doğrulama için değil.
REPO_SPINE = [  # llm_gateway.py AGENT_CHAINS / CHAINS'te fiilen kullanılanlar
    "anthropic/claude-sonnet-5",
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
    "google/gemini-3.7-flash",
    "x-ai/grok-4.6",
    "openai/gpt-5.6-sol-pro",  # live_llm_gate.py varsayılan hakemi (D-02)
]
CANDIDATES = [
    "x-ai/grok-4.20-multi-agent-0309",     # OSINT sentez yedek adayı
    "openai/gpt-5.6-luna",                 # "Nous indirimli frontier" iddiası
    "meta-llama/llama-3.3-70b-instruct",   # "FINAL KARAR" genel-chat satırı
    "google/gemma-3-27b-it",               # "FINAL KARAR" vision satırı
    "stepfun/step-3.7-flash:free",         # "FINAL KARAR" vision+video satırı
    "poolside/laguna:free",                # "FINAL KARAR" code-specialist satırı
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "upstage/solar-pro4:free",             # "FINAL KARAR" 524K satırı
    "upstage/solar-pro4",
    "inclusionai/ling-3.0-flash:free",
    "inclusionai/ling-3.0-flash",
    "meituan/longcat-2.0:free",            # "FINAL KARAR" 1M repo satırı
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "z-ai/glm-5.2",
    "z-ai/glm-5.3-flash",
    "alibaba/qwen3-vl-plus",
    "qwen/qwen3-vl-plus",
]


def _per_million(price: str | None) -> str:
    try:
        return f"${float(price) * 1_000_000:.4g}"
    except (TypeError, ValueError):
        return "?"


def main() -> int:
    with urllib.request.urlopen(CATALOG_URL, timeout=30) as resp:
        data = json.load(resp)["data"]
    by_id = {m["id"]: m for m in data}
    as_json = "--json" in sys.argv

    report = {"catalog_size": len(data), "candidates": {}, "spine": {}, "free_roster": []}

    def row(slug: str) -> dict:
        m = by_id.get(slug)
        if not m:
            return {"present": False}
        pricing = m.get("pricing") or {}
        return {
            "present": True,
            "context": m.get("context_length"),
            "in_per_1m": _per_million(pricing.get("prompt")),
            "out_per_1m": _per_million(pricing.get("completion")),
        }

    for slug in REPO_SPINE:
        report["spine"][slug] = row(slug)
    for slug in CANDIDATES:
        report["candidates"][slug] = row(slug)
    report["free_roster"] = sorted(s for s in by_id if s.endswith(":free"))

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Katalog: {len(data)} model (live, {CATALOG_URL})\n")
        print("== Repo omurgası (bunlardan biri YOKSA exit=1) ==")
        for slug, r in report["spine"].items():
            _print(slug, r)
        print("\n== FINAL-KARAR / aday iddiaları ==")
        for slug, r in report["candidates"].items():
            _print(slug, r)
        print(f"\n== Canlı :free kadrosu ({len(report['free_roster'])} slug) ==")
        for slug in report["free_roster"]:
            print(f"  {slug}")

    missing = [s for s, r in report["spine"].items() if not r["present"]]
    return 1 if missing else 0


def _print(slug: str, r: dict) -> None:
    if r["present"]:
        print(f"  ✅ {slug}  in={r['in_per_1m']} out={r['out_per_1m']} ctx={r['context']}")
    else:
        print(f"  ❌ {slug}  YOK")


if __name__ == "__main__":
    sys.exit(main())
