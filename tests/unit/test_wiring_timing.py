"""Wiring W1: timing forensics alan sozlesmesi (backend).

Adli denetim kaniti: analyze_timing night_share uretiyordu ama executor
night_owl_score okuyordu -> log hep 'gece %0'. Bu testler gercek anahtar
okundugunu kilitler.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_EXECUTOR_SRC = (REPO_ROOT / "agent_core" / "task_executor.py").read_text(encoding="utf-8")


def test_task_executor_reads_real_timing_keys():
    assert "night_share" in TASK_EXECUTOR_SRC
    assert "night_owl_score" not in TASK_EXECUTOR_SRC
    assert "peak_utc_hour" not in TASK_EXECUTOR_SRC
    assert "tz_offset_hours_likely" not in TASK_EXECUTOR_SRC


@pytest.mark.asyncio
async def test_executor_log_shows_real_night_share(tmp_path):
    """night_share=0.8 -> log '%80' demeli; '%0' degil."""
    from agent_core.services.canonical_memory import CanonicalMemory
    from agent_core.task_executor import PinealExecutor

    logs = []
    executor = PinealExecutor(log_callback=lambda lvl, msg: logs.append(msg))
    executor.memory = CanonicalMemory(str(tmp_path))
    times = [
        "2026-08-01T23:30:00",
        "2026-08-02T01:00:00",
        "2026-08-03T00:15:00",
        "2026-08-04T02:40:00",
        "2026-08-05T10:00:00",
    ]
    await executor.execute_task(
        {"target_profile": {"post_times": times, "posts": ["a", "b", "c", "d", "e"], "bio": "x"}},
        "fx_timing",
    )
    timing_lines = [l for l in logs if "ZAMAN FORENSİĞİ" in l]
    assert timing_lines, "ZAMAN FORENSİĞİ logu üretilmedi"
    assert "gece %80" in timing_lines[0], timing_lines[0]
