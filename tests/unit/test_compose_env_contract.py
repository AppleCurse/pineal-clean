"""[AUDIT R2] Compose + .env PINEAL_ENV akışının FAIL-CLOSED sözleşmesi.

Orijinal bulgu: Dockerfile ENV PINEAL_ENV=production (fail-closed) +
.env.example içinde AKTIF `PINEAL_ENV=development` + compose env_file
önceliği => reponun kendi önerdiği "cp .env.example .env && docker compose
up" akışı konteyneri sessizce development modunda (auth KAPALI) açardı.

Bu test akışı sözleşmeye bağlar:
  1. Compose explicit `PINEAL_ENV=${PINEAL_ENV:-production}` sabitler
     (env_file'daki değer artık ezemez).
  2. .env.example'da AKTIF PINEAL_ENV satırı YOKTUR (yalnız yorumlu örnek)
     -> interpolation default'ı (production) devralınır.
  3. Yerel geliştirme YALNIZCA açık seçimle: host env PINEAL_ENV=development.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_compose_pins_production_by_default():
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "PINEAL_ENV=${PINEAL_ENV:-production}" in compose, (
        "compose PINEAL_ENV'ü env_file'e bırakıyor: development sızması açık"
    )


def test_env_example_has_no_active_pineal_env_line():
    lines = (REPO / ".env.example").read_text(encoding="utf-8").splitlines()
    active = [
        ln for ln in lines
        if ln.strip().startswith("PINEAL_ENV=") and not ln.strip().startswith("#")
    ]
    assert not active, f".env.example'de AKTIF PINEAL_ENV satırı geri geldi: {active}"


def test_development_still_possible_explicitly():
    """Kullanıcı .env'e açıkça PINEAL_ENV=development yazar -> compose onu devralır.

    ${VAR:-default} semantiği: ortamda PINEAL_ENV varsa O kullanılır.
    (Bu sandbox'ta docker compose config çalıştırılamayabilir; şablon
    varlığını doğruluyoruz.)
    """
    compose_text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${PINEAL_ENV:-production}" in compose_text
