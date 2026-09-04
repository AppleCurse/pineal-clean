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
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Çok büyük promptları cache'lemekten kaçın (32 KB).
MAX_CACHABLE_PROMPT_CHARS = 32_000

# Varsayılan saklama süresi: 7 gün.
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

# [AUDIT P0-2] Sert satır tavanı: TTL'den bağımsız ikinci bir emniyet kemeri.
# Süresi dolan ama bir daha HİÇ okunmayan anahtarlar diskte kalıcı kalırdı.
DEFAULT_MAX_ROWS = 50_000

# Kaç yazma işleminden sonra tam budama (prune) yapılır (ikincil tetikleyici).
_PRUNE_EVERY_WRITES = 256

# [AUDIT P0-2 v2] Zaman temelli budama aralığı (birincil tetikleyici).
# Yazım sayısına bağlı tetikleyici düşük trafikte hiç çalışmıyordu.
DEFAULT_PRUNE_INTERVAL_SECONDS = 900


class ResponseCache:
    """SQLite tabanlı, TTL'li, thread-güvenli birebir yanıt cache'i."""

    def __init__(
        self,
        db_path: str = "./cache/responses.db",
        ttl_seconds: Optional[int] = DEFAULT_TTL_SECONDS,
        max_rows: int = DEFAULT_MAX_ROWS,
        prune_interval_seconds: float = DEFAULT_PRUNE_INTERVAL_SECONDS,
    ):
        self.enabled = True
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self.max_rows = max(1, int(max_rows))
        self.prune_interval_seconds = max(1.0, float(prune_interval_seconds))
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.pruned = 0
        self._writes_since_prune = 0
        # [AUDIT P0-2 v2] Budama tetikleyicisi eskiden YALNIZCA yazım sayısına
        # bağlıydı (her 256 yazım). Ölçülen boşluk: düşük trafikli ama benzersiz
        # anahtar üreten bir sistemde 256 eşiğine HİÇ ulaşılmıyor ve süresi
        # dolmuş ama bir daha okunmayan satırlar sonsuza dek diskte kalıyordu
        # (10 yazım + TTL doldu + okuma yok -> 10 satır diskte, pruned=0).
        # Çözüm: ZAMAN temelli son tarih. Her get/put tek bir float karşılaştırması
        # yapar (~50 ns); süre geçtiyse budama çalışır. Yazım-sayısı tetikleyicisi
        # yüksek trafikli iş yükleri için ikincil emniyet olarak kalır.
        self._prune_deadline = time.monotonic() + self.prune_interval_seconds
        # [AUDIT P0-6] Tek paylaşılan bağlantı + kilit. Eskiden her get/put yeni
        # bir sqlite3.connect() açıyordu: hem bağlanma maliyeti hem de WAL
        # olmadan yazıcı kilidi. Bağlantı artık yeniden kullanılıyor ve erişim
        # tek bir kilit ile serileştiriliyor (SQLite'ın istediği de bu).
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        # Açılışta bir kez buda: yeniden başlatma, birikmiş süresi dolmuş
        # satırları temizlemek için doğal bir fırsattır.
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        """Paylaşılan bağlantıyı döndürür; ilk çağrıda açar. Kilit İÇİNDE çağrılır."""
        if self._conn is not None:
            return self._conn
        if self.db_path != ":memory:":
            directory = os.path.dirname(self.db_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        if self.db_path != ":memory:":
            # [AUDIT P0-2] SIRA ÖNEMLİ: auto_vacuum yalnızca boş bir veritabanında
            # değişebilir ve "PRAGMA journal_mode=WAL" dosyayı başlatır. WAL
            # önce çalışırsa auto_vacuum sessizce 0 kalır (ölçülerek doğrulandı).
            # Not: mevcut bir db için bir kez "PRAGMA auto_vacuum=INCREMENTAL;
            # VACUUM;" gerekir; yeni kurulumlarda otomatik etkinleşir.
            conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
            # WAL: yazıcı okuyucuyu bloke etmez; NORMAL fsync maliyetini düşürür.
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        self._conn = conn
        return conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None

    def _init_db(self) -> None:
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS response_cache (
                        key        TEXT PRIMARY KEY,
                        value      TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL
                    )
                    """
                )
                # [AUDIT P0-2 v2] Süre SATIRDA saklanır. Eskiden yalnızca
                # created_at tutuluyor ve süre her okumada GÜNCEL config'ten
                # yeniden hesaplanıyordu: PINEAL_CACHE_TTL 7 gün -> 1 sn
                # yapılınca 7 günlük kayıt 1.2 sn'de yok oluyordu; 1 sn ->
                # süresiz yapılınca süresi dolmuş kayıt sonsuza dek yaşıyordu.
                # Mevcut veritabanları için tek seferlik göç + doldurma.
                columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(response_cache)")
                }
                if "expires_at" not in columns:
                    conn.execute("ALTER TABLE response_cache ADD COLUMN expires_at REAL")
                    logger.warning(
                        "ResponseCache göçü: expires_at kolonu eklendi; mevcut satırlar "
                        "güncel PINEAL_CACHE_TTL (%s) ile dolduruldu.", self.ttl_seconds,
                    )
                if self.ttl_seconds is not None:
                    conn.execute(
                        "UPDATE response_cache SET expires_at = created_at + ? "
                        "WHERE expires_at IS NULL",
                        (self.ttl_seconds,),
                    )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rc_created ON response_cache(created_at)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rc_expires ON response_cache(expires_at)"
                )
                conn.commit()
        except Exception as exc:  # cache asla ana akışı bozmamalı
            logger.warning("ResponseCache başlatılamadı, cache devre dışı: %s", exc)
            self.errors += 1
            # [AUDIT] Telemetri yalan söylemesin: başlatılamayan cache
            # "enabled": True raporlamaz.
            self.enabled = False

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

    def _maybe_prune(self) -> None:
        """Zamanı geldiyse buda. Her get/put'ta tek float karşılaştırması."""
        if time.monotonic() >= self._prune_deadline:
            self.prune()

    def get(self, key: str) -> Optional[str]:
        self._maybe_prune()
        try:
            with self._lock:
                row = self._connect().execute(
                    "SELECT value, expires_at FROM response_cache WHERE key = ?",
                    (key,),
                ).fetchone()
                if row is not None and self._is_expired(row[1]):
                    # [AUDIT P0-2] Süresi dolan satır burada SİLİNİR. Eskiden
                    # yalnızca yok sayılıyordu ve diskte süresiz kalıyordu.
                    self._connect().execute(
                        "DELETE FROM response_cache WHERE key = ?", (key,)
                    )
                    self._connect().commit()
                    self.pruned += 1
                    row = None

            if row is None:
                self.misses += 1
                return None

            self.hits += 1
            return row[0]
        except Exception as exc:
            logger.warning("Cache okuma hatası: %s", exc)
            self.errors += 1
            self.misses += 1
            return None

    def _is_expired(self, expires_at: Optional[float]) -> bool:
        # [AUDIT P0-2 v2] Süre SATIRDAN okunur, config'ten türetilmez.
        # expires_at IS NULL -> süresiz (ttl_seconds=None yazım sözleşmesi).
        # ttl_seconds=0 -> expires_at == yazım anı -> anında süresi dolar.
        if expires_at is None:
            return False
        return time.time() > float(expires_at)

    def put(self, key: str, value: str) -> None:
        if not value:
            return
        try:
            with self._lock:
                conn = self._connect()
                now = time.time()
                expires_at = None if self.ttl_seconds is None else now + self.ttl_seconds
                conn.execute(
                    "INSERT OR REPLACE INTO response_cache "
                    "(key, value, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (key, value, now, expires_at),
                )
                conn.commit()
                self._writes_since_prune += 1
                due = self._writes_since_prune >= _PRUNE_EVERY_WRITES
                if due:
                    self._writes_since_prune = 0
            if due or time.monotonic() >= self._prune_deadline:
                self.prune()
        except Exception as exc:
            logger.warning("Cache yazma hatası: %s", exc)
            self.errors += 1

    def prune(self) -> int:
        """[AUDIT P0-2] Süresi dolmuş ve tavanı aşan satırları kalıcı siler.

        Dönen değer silinen satır sayısıdır. Budama hiçbir zaman ana akışı
        bozmaz; hata yalnızca loglanır ve sayaca yazılır. Son tarih her
        çağrıda (başarılı ya da değil) yenilenir; aksi halde budama hatası
        sürekli yeniden denenir ve her işlemde kilit çekişmesi yaratır.
        """
        self._prune_deadline = time.monotonic() + self.prune_interval_seconds
        try:
            with self._lock:
                conn = self._connect()
                deleted = 0
                # [AUDIT P0-2 v2] cutoff config'ten değil satırın kendi
                # expires_at değerinden; böylece TTL değişikliği mevcut
                # satırların ömrünü yeniden yorumlamaz.
                deleted += conn.execute(
                    "DELETE FROM response_cache "
                    "WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),),
                ).rowcount or 0
                if self.max_rows:
                    deleted += conn.execute(
                        "DELETE FROM response_cache WHERE key NOT IN ("
                        "  SELECT key FROM response_cache ORDER BY created_at DESC LIMIT ?"
                        ")",
                        (self.max_rows,),
                    ).rowcount or 0
                conn.commit()
                if deleted:
                    self.pruned += deleted
                    conn.execute("PRAGMA incremental_vacuum")
                return deleted
        except Exception as exc:
            logger.warning("Cache budanamadı: %s", exc)
            self.errors += 1
            return 0

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "enabled": bool(self.enabled),
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "pruned_rows": self.pruned,
            "hit_rate": f"{(self.hits / total * 100):.1f}%" if total else "0.0%",
        }


class NullCache:
    """Cache kapatıldığında kullanılan hiçbir şey yapmayan yedek."""

    enabled = False
    hits = 0
    misses = 0
    errors = 0
    pruned = 0

    def is_cachable(self, prompt: str, images: Optional[list]) -> bool:
        return False

    def get(self, key: str) -> None:
        return None

    def put(self, key: str, value: str) -> None:
        return None

    def prune(self) -> int:
        return 0

    def close(self) -> None:
        return None

    def stats(self) -> dict:
        # ResponseCache.stats() ile aynı sözleşme: tüketici tarafında
        # KeyError riski olmasın diye tüm alanlar mevcut.
        return {
            "enabled": False,
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "pruned_rows": 0,
            "hit_rate": "0.0%",
        }


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
    try:
        max_rows = int(os.getenv("PINEAL_CACHE_MAX_ROWS", str(DEFAULT_MAX_ROWS)))
    except ValueError:
        max_rows = DEFAULT_MAX_ROWS
    try:
        prune_interval = float(os.getenv(
            "PINEAL_CACHE_PRUNE_INTERVAL_SECONDS",
            str(DEFAULT_PRUNE_INTERVAL_SECONDS),
        ))
    except ValueError:
        prune_interval = DEFAULT_PRUNE_INTERVAL_SECONDS
    return ResponseCache(
        db_path=db_path,
        ttl_seconds=ttl,
        max_rows=max_rows,
        prune_interval_seconds=prune_interval,
    )
