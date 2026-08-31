"""Production container security and runtime-content contract."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _dockerfile_lines():
    assert DOCKERFILE.exists(), f"Dockerfile bulunamadi: {DOCKERFILE}"
    return DOCKERFILE.read_text(encoding="utf-8").splitlines()


def test_dockerfile_copies_config_directory():
    lines = _dockerfile_lines()
    assert "COPY config/ ./config/" in [line.strip() for line in lines]


def test_dockerfile_defaults_to_fail_closed_production_profile():
    content = "\n".join(_dockerfile_lines())
    assert "PINEAL_ENV=production" in content


def test_dockerfile_healthcheck_uses_public_startup_health_only():
    content = " ".join(line.strip() for line in _dockerfile_lines())
    assert "http://127.0.0.1:8000/health" in content
    assert "/api/telemetry" not in content
    assert "PINEAL_TOKEN" not in next(
        line for line in _dockerfile_lines() if "CMD python -c" in line
    )
