"""B3: Dockerfile kontrat kilidi.

Docker imajı, DecisionConfig'in ihtiyaç duydugu config/ dizinini
tasiMAZSA konteyner start'ta 'FileNotFoundError: Decision config not found'
ile coker (adli denetimde kanitlandi). Bu testler o regresyonun sessizce
geri gelmesini engeller:

1. Imaj iceriginde config/ KOPYALANMALI (COPY config/ ./config/).
2. HEALTHCHECK, PINEAL_TOKEN tanimliyken X-API-Key tasimali; aksi halde
   auth modunda surekli 401 -> unhealthy olur.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _dockerfile_lines():
    assert DOCKERFILE.exists(), f"Dockerfile bulunamadi: {DOCKERFILE}"
    return DOCKERFILE.read_text(encoding="utf-8").splitlines()


def test_dockerfile_copies_config_directory():
    """B3 kapisi: runtime asamasi config/ dizinini imaja tasimak zorunda."""
    lines = _dockerfile_lines()
    assert "COPY config/ ./config/" in [line.strip() for line in lines], (
        "Dockerfile config/ dizinini kopyalamiyor; konteyner start'ta "
        "config_loader.py: 'Decision config not found' ile coker."
    )


def test_dockerfile_healthcheck_is_token_aware():
    """B3 kapisi: PINEAL_TOKEN set'liyken healthcheck 401 yememeli."""
    lines = _dockerfile_lines()
    healthcheck = " ".join(
        line.strip() for line in lines if line.strip().startswith(("HEALTHCHECK", "CMD"))
    )
    assert "PINEAL_TOKEN" in healthcheck, "Healthcheck env token'ini okumuyor"
    assert "X-API-Key" in healthcheck, "Healthcheck X-API-Key header'i tasimiyor"
