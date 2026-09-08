"""
token_compressor.py

PINEAL-HERETIC RTK Entegrasyonu — Python Mirror (ÜRÜNDE FİİLEN ÇALIŞAN KOD)

=============================================================================
MIRROR PATTERN NOTU
=============================================================================
Phase 9 Decision B gereği native çekirdek, Python ürün hattına PyO3/maturin
üzerinden BAĞLANAMAZ (bkz. tests/unit/test_rust_runtime_status.py).
Bu dosya, native bileşen ile MANTIKSAL OLARAK ÖZDEŞ saf Python
implementasyonudur ve gerçekte llm_gateway.py tarafından çağrılan versiyondur.

İki implementasyon ortak fixtures/compression_cases.json dosyasından ORTAK test
vakaları okur. Biri diğerinden saparsa ilgili test paketi kırmızı düşer —
sessiz sapma riski bu şekilde ortadan kaldırılmıştır.

=============================================================================
ADLİ TASARIM İLKESİ (Fail-Open Gerekçesi)
=============================================================================
Pineal'in genel doktrini "fail-closed"tur (Bayesian Epistemik Kapı,
quota_governor.UnknownQuotaDenied, PINEAL_ALLOW_PAID_ESCALATION).
Bu modül BİLEREK farklı davranır: FAIL-OPEN.

Gerekçe: Bu modül KANIT üretmez, HARCAMA kararı vermez, EPİSTEMİK
sonuca varmaz. Yalnızca dış API'ye giden bir prompt'un token boyutunu
düşüren PERFORMANS optimizasyonudur. Çökerse sistem "belirsizlik" veya
"sahte kanıt" üretmez — sadece daha uzun/pahalı bir prompt gönderilir.
Bu yüzden başarısızlık "dur" değil, "orijinali kullan" ile sonuçlanır.

=============================================================================
SAFLIK GARANTİSİ
=============================================================================
Bu modül:
  - Dosya sistemine YAZMAZ (fixture/config OKUMA hariç yoktur — bu
    dosya hiçbir dosya okumaz da, saf string->string fonksiyondur)
  - Ağa dokunmaz
  - CanonicalMemory, HindsightMemory, task_executor'ı İMPORT ETMEZ
  - Girdi: str, Çıktı: str. Yan etki yoktur.
Bkz. tests/unit/test_token_compressor_purity.py
"""

from __future__ import annotations

import json
import re
from enum import Enum


class CompressionLevel(str, Enum):
    """
    Sıkıştırma stratejisi seçenekleri.
    Agresiflik arttıkça geri-alınamazlık riski artar — varsayılan
    her zaman en muhafazakâr seviyedir.
    """
    CONSERVATIVE = "conservative"  # Sadece boşluk/satır temizliği. Anlam kaybı riski SIFIR.
    STANDARD = "standard"          # Conservative + tek-satır JSON minify + ardışık dedupe.


_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")


def compress_prompt(input_text: str, level: CompressionLevel | str = CompressionLevel.CONSERVATIVE) -> str:
    """
    Ana giriş noktası. Girdi metnini verilen seviyeye göre sıkıştırır.

    Garantiler:
        - Exception fırlatmaz (iç hata durumunda orijinal input döner —
          fail-open modül-içi seviyede de uygulanır).
        - Girdi boşsa/sadece whitespace ise aynen döner.
        - Çıktı her zaman str'dir.

    Args:
        input_text: Sıkıştırılacak ham metin.
        level: CompressionLevel enum değeri veya "conservative"/"standard" string'i.

    Returns:
        Sıkıştırılmış metin, veya herhangi bir iç hata durumunda orijinal input_text.
    """
    try:
        if not input_text or not input_text.strip():
            return input_text

        level = CompressionLevel(level) if not isinstance(level, CompressionLevel) else level

        stage1 = _collapse_whitespace(input_text)

        if level == CompressionLevel.CONSERVATIVE:
            return stage1

        stage2 = _try_minify_json_lines(stage1)
        return _dedupe_boilerplate_lines(stage2)

    except Exception:
        return input_text


def _collapse_whitespace(text: str) -> str:
    """
    Aşama 1: Fazlalık boşluk ve satır temizliği (anlam-nötr, sözdizimsel).

    Kurallar:
        - Ardışık boşluk/tab -> tek boşluk
        - 3+ ardışık yeni satır -> 2 yeni satır (paragraf ayrımı korunur)
        - Satır sonu trailing whitespace silinir
        - CRLF -> LF normalizasyonu
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _MULTI_SPACE_RE.sub(" ", normalized)
    normalized = _EXCESS_NEWLINES_RE.sub("\n\n", normalized)
    lines = [line.rstrip() for line in normalized.splitlines()]
    return "\n".join(lines)


def _try_minify_json_lines(text: str) -> str:
    """
    Aşama 2 (Standard): Yalnızca TEK SATIRLIK geçerli JSON'ları minify eder.

    GÜVENLİK KISITI: Çok satırlı / iç içe JSON tespiti YAPILMAZ.
    Doğrulanamayan blok orijinal haliyle bırakılır (ya tam minify, ya hiç).
    """
    result_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        looks_like_json = (
            (stripped.startswith("{") and stripped.endswith("}"))
            or (stripped.startswith("[") and stripped.endswith("]"))
        )
        if looks_like_json:
            try:
                parsed = json.loads(stripped)
                result_lines.append(json.dumps(parsed, separators=(",", ":"), ensure_ascii=False))
            except (json.JSONDecodeError, ValueError):
                result_lines.append(line)
        else:
            result_lines.append(line)
    return "\n".join(result_lines)


def _dedupe_boilerplate_lines(text: str, max_consecutive_repeats: int = 2) -> str:
    """
    Aşama 3 (Standard): Ardışık tekrarlayan satırları eler.

    GÜVENLİK KISITI: Yalnızca TAM AYNI, ARDIŞIK satırlar hedeflenir.
    Uzak mesafeli tekrarlara (ör. kasıtlı bio üslubu) dokunulmaz.
    """
    result = []
    last_line = None
    repeat_count = 0

    for line in text.splitlines():
        if line == last_line and line.strip():
            repeat_count += 1
            if repeat_count < max_consecutive_repeats:
                result.append(line)
        else:
            repeat_count = 0
            result.append(line)
            last_line = line

    return "\n".join(result)