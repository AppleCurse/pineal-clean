"""Wiring W1/W2/W3 (frontend): UI yalniz gercek model alanlarini okur.

Svelte test altyapisi olmadigindan kaynak-kontrat kilitleri kullanilir:
eski sahte anahtarlar (night_owl_score, bot_probability, ritual_match_score...)
frontend kaynaginda bir daha GECEMEZ.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL_SRC = (
    REPO_ROOT / "frontend" / "src" / "components" / "UnifiedCompactPanel.svelte"
).read_text(encoding="utf-8")
I18N_SRC = (REPO_ROOT / "frontend" / "src" / "i18n.ts").read_text(encoding="utf-8")


def test_frontend_reads_real_timing_keys():
    assert "night_share" in PANEL_SRC
    assert "peak_hour" in PANEL_SRC
    assert "median_drift_hours" in PANEL_SRC
    assert "night_owl_score" not in PANEL_SRC
    assert "peak_utc_hour" not in PANEL_SRC
    assert "tz_offset_hours_likely" not in PANEL_SRC


def test_frontend_reads_verdict_code_not_bot_probability():
    assert "verdict_code" in PANEL_SRC
    assert "bot_probability" not in PANEL_SRC


def test_frontend_reads_only_real_resonance_fields():
    assert "compatibility_score" in PANEL_SRC
    assert "recommended_approach" in PANEL_SRC
    assert "red_flags" in PANEL_SRC
    assert "ritual_match_score" not in PANEL_SRC
    assert "playlist_resonance" not in PANEL_SRC
    assert "envy_intensity" not in PANEL_SRC


def test_i18n_uses_real_labels_only():
    assert "verdictHealthy" in I18N_SRC
    assert "verdictInflated" in I18N_SRC
    assert "engagementRateLabel" in I18N_SRC
    assert "resonanceScoreLabel" in I18N_SRC
    assert "approachLabel" in I18N_SRC
    assert "redFlagsLabel" in I18N_SRC
    assert "botProbLabel" not in I18N_SRC
    assert "ritualMatch" not in I18N_SRC
    assert "playlistResonance" not in I18N_SRC
    assert "envyIntensity" not in I18N_SRC
