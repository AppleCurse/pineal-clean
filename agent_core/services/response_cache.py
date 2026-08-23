"""
Birebir (exact) yanıt önbelleği — LLM maliyetini ve gecikmeyi düşürür.

Tasarım gerekçesi:
- Bu bir "anlamsal/semantik" cache DEĞİLDİR. Aynı (model, system_prompt,
  sıcaklık, prompt) bileşeni için birebir aynı hash kullanılır; böylece iki
  BENZER ama FARKLI profilin çakışma/zehirlenme riski yoktur ("sıfır halüsinasyon"
  önceliğiyle tutarlı).
- Harici ağır bağımlılık (GPTCache/FAISS/ONNX/torch) YOKTUR; yalnızca stdlib
  sqlite3 kullanır. Bu sayede CI ve baslat.bat akışı yavaşlamaz.
- İleride anlamsal cache (GPTCache) istenirse, `get/put` arayüzü aynı kalacak
  şekilde bu sınıfın yerine başka bir uygulama konabilir.

Cache yalnızca şu durumlarda devreye girer (LLMGateway tarafından zorlanır):
  * salt-metin istekleri (görsel/vision çağrıları hariç)
  * makul uzunluktaki prompt'lar
  * PINEAL_RESPONSE_CACHE=0 ile kapatılmadıkça
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Çok büyük promptları cache'lemekten kaçın (32 KB).
MAX_CACHABLE_PROMPT_CHARS = 32_000

# Varsayılan saklama süresi: 7 gün.
DEFAULT_TTL_SECONDS = 7 * 24 * 3600


class ResponseCache:
    """SQLite tabanlı, TTL'li, thread-güvenli birebir yanıt cache'i."""

    def __init__(
        self,
        db_path: str = "./cache/responses.db",
        ttl_seconds: Optional[int] = DEFAULT_TTL_SECONDS,
    ):
        self.enabled = True
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        return sqlite3.connect(self.db_path, timeout=5)

    def _init_db(self) -> None:
        try:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS response_cache (
                        key        TEXT PRIMARY KEY,
                        value      TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rc_created ON response_cache(created_at)"
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:  # cache asla ana akışı bozmamalı
            logger.warning("ResponseCache başlatılamadı, cache devre dışı: %s", exc)
            self.errors += 1

    @staticmethod
    def make_key(
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """İsteği benzersiz şekilde tanımlayan SHA-256 anahtarı üretir.

        YALNIZCA prompt değil; model, system_prompt ve sıcaklık da dahil edilir.
        Aksi halde farklı modellerin/kişiliklerin yanıtları birbirine karışır.
        """
        payload = json.dumps(
            {
                "m": model or "",
                "s": system_prompt or "",
                "t": round(float(temperature), 3),
                "p": prompt,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def is_cachable(self, prompt: str, images: Optional[list]) -> bool:
        if images:
            return False
        if not prompt:
            return False
        if len(prompt) > MAX_CACHABLE_PROMPT_CHARS:
            return False
        return True

    def get(self, key: str) -> Optional[str]:
        try:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT value, created_at FROM response_cache WHERE key = ?",
                    (key,),
                ).fetchone()
            finally:
                conn.close()

            if row is None:
                self.misses += 1
                return None

            value, created_at = row
            if self.ttl_seconds and (time.time() - float(created_at)) > self.ttl_seconds:
                # Süresi dolmuş — yoksay (yeni değerin üzerine yazılacak)
                self.misses += 1
                return None

            self.hits += 1
            return value
        except Exception as exc:
            logger.warning("Cache okuma hatası: %s", exc)
            self.errors += 1
            self.misses += 1
            return None

    def put(self, key: str, value: str) -> None:
        if not value:
            return
        try:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO response_cache (key, value, created_at) "
                    "VALUES (?, ?, ?)",
                    (key, value, time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("Cache yazma hatası: %s", exc)
            self.errors += 1

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "enabled": True,
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate": f"{(self.hits / total * 100):.1f}%" if total else "0.0%",
        }


class NullCache:
    """Cache kapatıldığında kullanılan hiçbir şey yapmayan yedek."""

    enabled = False
    hits = 0
    misses = 0

    def is_cachable(self, prompt: str, images: Optional[list]) -> bool:
        return False

    def get(self, key: str) -> None:
        return None

    def put(self, key: str, value: str) -> None:
        return None

    def stats(self) -> dict:
        return {"enabled": False}


def build_cache_from_env() -> "ResponseCache | NullCache":
    """PINEAL_RESPONSE_CACHE / PINEAL_CACHE_PATH ayarlarına göre cache kurar."""
    enabled = os.getenv("PINEAL_RESPONSE_CACHE", "1").strip().lower()
    if enabled in ("0", "false", "no", "off"):
        logger.info("ResponseCache PINEAL_RESPONSE_CACHE=%s ile kapatıldı.", enabled)
        return NullCache()

    db_path = os.getenv("PINEAL_CACHE_PATH", "./cache/responses.db")
    try:
        ttl = int(os.getenv("PINEAL_CACHE_TTL", str(DEFAULT_TTL_SECONDS)))
    except ValueError:
        ttl = DEFAULT_TTL_SECONDS
    return ResponseCache(db_path=db_path, ttl_seconds=ttl)
