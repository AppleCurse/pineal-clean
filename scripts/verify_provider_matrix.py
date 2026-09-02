#!/usr/bin/env python3
"""Sağlayıcı matrisi doğrulayıcı — "eldeki anahtarlar gerçekten çalışıyor mu?"
sorusunu her sağlayıcının KENDİ hesabına sorarak cevaplar.

Neden var: anahtarların hazır olması hesabın erişebilir olduğu anlamına gelmez.
Bu betik her sağlayıcı için GET {BASE}/models çağrısı yapar ve dürüst raporlar:

    - ERİŞİM VAR/YOK (HTTP 401/403 -> anahtar reddedildi; ağ hatası -> ayrı basılır)
    - hesabın gördüğü model sayısı
    - kodda kullanılan rotaların (TOHUMLAR) hesap kataloğunda VAR/YOK damgası   -- bu tartışmayı bitiren satırdır

Kurallar (verify_nous_catalog.py ile aynı disiplin):
  - Anahtarlar yalnız env'den okunur, asla basılmaz/saklanmaz.
  - Ağ çıktısı diske yazılmaz; yalnız stdout.
  - Bir sağlayıcının anahtarı tanımsızsa ATLANDI basılır (hata değil).
  - Hiçbir sağlayıcı doğrulanamazsa exit 2 (fail-closed).

Kullanım:
    export NOUS_API_KEY=...
    export OPENROUTER_API_KEY=...        # isteğe bağlı
    export GROQ_API_KEY=...              # isteğe bağlı
    python3 scripts/verify_provider_matrix.py            # insan okur
    python3 scripts/verify_provider_matrix.py --json     # makine okur
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Sağlayıcı ve rota slugh'ları TEK KAYNAKTAN: agent_core/services/llm_gateway_v2.py
# içindeki listeden alınmıştır (2026-09-02). Burada "beklenen" olmaları doğruluk
# iddiası değildir — betiğin tek işi VAR/YOK damgalamaktır.
PROVIDERS = [
    {
        "name": "nous",
        "env": "NOUS_API_KEY",
        "base_env": "NOUS_API_BASE",
        "base": "https://inference-api.nousresearch.com/v1",
        "seeds": [
            "openai/gpt-5.6-luna",        # paid omurga (kullanıcı dashboard kanıtlı)
            "anthropic/claude-sonnet-5",  # paid omurga
            "stepfun/step-3.7-flash:free",
            "upstage/solar-pro4:free",
            "meituan/longcat-2.0:free",
            "poolside/laguna:free",
        ],
    },
    {
        "name": "openrouter",
        "env": "OPENROUTER_API_KEY",
        "base_env": "OPENROUTER_BASE_URL",
        "base": "https://openrouter.ai/api/v1",
        "seeds": [
            "anthropic/claude-sonnet-5",   # .env.example Tier-1
            "deepseek/deepseek-v4-flash",  # .env.example Tier-2
            "google/gemini-3.7-flash",     # .env.example vision
        ],
    },
    {
        "name": "groq",
        "env": "GROQ_API_KEY",
        "base_env": "GROQ_BASE_URL",
        "base": "https://api.groq.com/openai/v1",
        "seeds": [
            "openai/gpt-oss-120b",  # llm_gateway_v2 free fast-worker
            "openai/gpt-oss-20b",
        ],
    },
]


def _fetch_models(base: str, key: str) -> tuple[list | None, str]:
    """Döner: (data listesi | None, durum notu). Hiçbir istisna sızmaz."""
    req = urllib.request.Request(
        base.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        data = payload.get("data", payload if isinstance(payload, list) else [])
        return list(data), "OK"
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}" + (" — ANAHTAR REDDEDİLDİ" if e.code in (401, 403) else "")
    except urllib.error.URLError as e:
        return None, f"AĞ HATASI: {e.reason}"
    except Exception as e:  # JSON bozuk vs.
        return None, f"OKUNAMADI: {type(e).__name__}"


def main() -> int:
    as_json = "--json" in sys.argv
    report = {"providers": {}}
    any_verified = False

    for p in PROVIDERS:
        key = os.getenv(p["env"], "").strip()
        base = os.getenv(p["base_env"], p["base"]).rstrip("/")
        if not key:
            report["providers"][p["name"]] = {"skipped": True, "reason": f"{p['env']} tanımsız"}
            continue

        data, note = _fetch_models(base, key)
        if data is None:
            report["providers"][p["name"]] = {"reachable": False, "note": note}
            continue

        any_verified = True
        ids = {m.get("id") for m in data if isinstance(m, dict)}
        seeds = {s: (s in ids) for s in p["seeds"]}
        report["providers"][p["name"]] = {
            "reachable": True,
            "model_count": len(ids),
            "seeds": seeds,
        }

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=== SAĞLAYICI MATRİSİ DOĞRULAMA (hesaptan canlı) ===")
        for name, r in report["providers"].items():
            if r.get("skipped"):
                print(f"\n[{name}] ATLANDI — {r['reason']}")
                continue
            if not r.get("reachable"):
                print(f"\n[{name}] ERİŞİM YOK — {r['note']}")
                continue
            print(f"\n[{name}] ERİŞİM VAR — hesap {r['model_count']} model görüyor")
            for slug, ok in r["seeds"].items():
                print(f"    {'VAR ✓' if ok else 'YOK ✗'}  {slug}")
        print("\nNot: 'YOK' basılan rota kodda kullanılmamalı ya da slug güncellenmeli.")

    if not report["providers"]:
        print("HATA: hiçbir sağlayıcı anahtarı tanımlı değil (env boş).", file=sys.stderr)
        return 2
    return 0 if any_verified else 2


if __name__ == "__main__":
    raise SystemExit(main())
