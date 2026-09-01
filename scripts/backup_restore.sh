#!/usr/bin/env bash
# PINEAL-HERETIC — Yedekleme / Geri Yükleme Aracı
#
# Kullanım:
#   ./scripts/backup_restore.sh backup          → ./backups/pineal_YYYYMMDD_HHMMSS.tar.gz
#   ./scripts/backup_restore.sh restore <dosya> → memory/ ve cache/ geri yüklenir
#   ./scripts/backup_restore.sh list            → mevcut yedek listesi (SHA-256 kontrolüyle)
#   ./scripts/backup_restore.sh verify <dosya>  → yedek bütünlüğünü doğrula
#
# Kritik dizinler:
#   memory/  → görev kanıt zinciri JSON (KAYIP = GERİ ALINAMAZ VERİ KAYBI)
#   cache/   → SQLite response cache    (kaybedilebilir; yeniden doldurulur)
#
# Docker volume ortamında:
#   docker run --rm \
#     -v pineal_memory:/app/memory \
#     -v pineal_cache:/app/cache \
#     -v "$(pwd)/backups:/app/backups" \
#     pineal bash scripts/backup_restore.sh backup
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
MEMORY_DIR="${PINEAL_MEMORY_DIR:-$REPO_ROOT/memory}"
CACHE_DIR="${PINEAL_CACHE_DIR:-$REPO_ROOT/cache}"
BACKUP_DIR="${PINEAL_BACKUP_DIR:-$REPO_ROOT/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

log()  { echo "[PINEAL-BACKUP] $*"; }
warn() { echo "[PINEAL-BACKUP] ⚠  $*" >&2; }
die()  { echo "[PINEAL-BACKUP] ✗  $*" >&2; exit 1; }

cmd="${1:-help}"

case "$cmd" in

  backup)
    mkdir -p "$BACKUP_DIR"
    ARCHIVE="$BACKUP_DIR/pineal_${TIMESTAMP}.tar.gz"

    [[ -d "$MEMORY_DIR" ]] || die "Memory dizini bulunamadı: $MEMORY_DIR"

    INCLUDE_ARGS=(-C "$(dirname "$MEMORY_DIR")" "$(basename "$MEMORY_DIR")")
    if [[ -d "$CACHE_DIR" ]]; then
      INCLUDE_ARGS+=(-C "$(dirname "$CACHE_DIR")" "$(basename "$CACHE_DIR")")
    else
      warn "Cache dizini yok — yalnızca memory/ yedekleniyor."
    fi

    tar -czf "$ARCHIVE" "${INCLUDE_ARGS[@]}"
    sha256sum "$ARCHIVE" > "${ARCHIVE}.sha256"

    TASK_COUNT=$(find "$MEMORY_DIR" -maxdepth 1 -name "*.json" ! -name "learnings.json" 2>/dev/null | wc -l)
    log "✓ Yedek oluşturuldu : $ARCHIVE"
    log "  Görev sayısı      : $TASK_COUNT"
    log "  Boyut             : $(du -sh "$ARCHIVE" | cut -f1)"
    log "  SHA-256           : $(cut -d' ' -f1 "${ARCHIVE}.sha256")"
    ;;

  restore)
    ARCHIVE="${2:-}"
    [[ -z "$ARCHIVE" ]] && die "Kullanım: $0 restore <yedek.tar.gz>"
    [[ -f "$ARCHIVE" ]]  || die "Yedek dosyası bulunamadı: $ARCHIVE"

    SHA_FILE="${ARCHIVE}.sha256"
    if [[ -f "$SHA_FILE" ]]; then
      log "SHA-256 doğrulanıyor…"
      sha256sum --check "$SHA_FILE" || die "SHA-256 uyumsuz — yedek bozuk olabilir!"
      log "✓ Bütünlük doğrulandı."
    else
      warn "SHA-256 dosyası yok (${SHA_FILE}) — doğrulama atlandı."
    fi

    # Mevcut memory/ dizinini önce yedekle (pre-restore)
    if [[ -d "$MEMORY_DIR" ]]; then
      mkdir -p "$BACKUP_DIR"
      PRE="$BACKUP_DIR/pre_restore_memory_${TIMESTAMP}.tar.gz"
      tar -czf "$PRE" -C "$(dirname "$MEMORY_DIR")" "$(basename "$MEMORY_DIR")"
      warn "Mevcut memory/ → $PRE (geri alma için saklandı)"
    fi

    RESTORE_TMP="$(mktemp -d)"
    trap 'rm -rf "$RESTORE_TMP"' EXIT

    log "Arşiv açılıyor: $ARCHIVE"
    tar -xzf "$ARCHIVE" -C "$RESTORE_TMP"

    if [[ -d "$RESTORE_TMP/memory" ]]; then
      rm -rf "$MEMORY_DIR"
      mv "$RESTORE_TMP/memory" "$MEMORY_DIR"
      TASK_COUNT=$(find "$MEMORY_DIR" -maxdepth 1 -name "*.json" ! -name "learnings.json" 2>/dev/null | wc -l)
      log "✓ memory/ geri yüklendi. Görev sayısı: $TASK_COUNT"
    else
      warn "Arşivde memory/ dizini yok."
    fi

    if [[ -d "$RESTORE_TMP/cache" ]]; then
      rm -rf "$CACHE_DIR"
      mv "$RESTORE_TMP/cache" "$CACHE_DIR"
      log "✓ cache/ geri yüklendi."
    fi

    log "✓ Geri yükleme tamamlandı."
    ;;

  list)
    if [[ ! -d "$BACKUP_DIR" ]]; then
      log "Henüz yedek yok: $BACKUP_DIR"
      exit 0
    fi
    log "Yedekler ($BACKUP_DIR):"
    find "$BACKUP_DIR" -maxdepth 1 -name "pineal_*.tar.gz" | sort | while read -r f; do
      SIZE=$(du -sh "$f" | cut -f1)
      SHA_OK=""
      if [[ -f "${f}.sha256" ]]; then
        sha256sum --check "${f}.sha256" &>/dev/null \
          && SHA_OK=" ✓sha256" || SHA_OK=" ✗sha256(BOZUK!)"
      fi
      echo "  $f  [$SIZE]${SHA_OK}"
    done
    ;;

  verify)
    ARCHIVE="${2:-}"
    [[ -z "$ARCHIVE" ]] && die "Kullanım: $0 verify <yedek.tar.gz>"
    [[ -f "$ARCHIVE" ]]  || die "Dosya bulunamadı: $ARCHIVE"

    SHA_FILE="${ARCHIVE}.sha256"
    if [[ -f "$SHA_FILE" ]]; then
      sha256sum --check "$SHA_FILE" && log "✓ SHA-256 bütünlük geçerli." || die "✗ SHA-256 uyumsuz!"
    else
      warn "SHA-256 dosyası yok — içerik testi yapılıyor."
    fi

    tar -tzf "$ARCHIVE" > /dev/null && log "✓ Arşiv açılabilir." || die "✗ Arşiv bozuk!"
    TASK_COUNT=$(tar -tzf "$ARCHIVE" | grep -c "memory/.*\.json" || true)
    log "  Arşivdeki görev JSON sayısı: $TASK_COUNT"
    ;;

  help|*)
    echo "Kullanım: $0 {backup|restore <dosya>|list|verify <dosya>}"
    echo ""
    echo "  backup            → Yeni yedek oluştur (memory/ + cache/)"
    echo "  restore <dosya>   → Yedeği geri yükle (önceki memory/ otomatik yedeklenir)"
    echo "  list              → Mevcut yedekleri listele (SHA-256 kontrolü)"
    echo "  verify <dosya>    → Yedek bütünlüğünü doğrula"
    echo ""
    echo "Ortam değişkenleri:"
    echo "  PINEAL_MEMORY_DIR  → varsayılan: ./memory"
    echo "  PINEAL_CACHE_DIR   → varsayılan: ./cache"
    echo "  PINEAL_BACKUP_DIR  → varsayılan: ./backups"
    ;;
esac
