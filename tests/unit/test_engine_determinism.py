"""Determinism tests for SeismosEngine event IDs and analysis outputs."""
import pytest
from agent_core.engines.seismos_engine import SeismosEngine


@pytest.mark.asyncio
async def test_seismos_engine_event_id_determinism():
    """Identical post series must generate identical event IDs and report metrics across multiple runs."""
    posts = [
        "Harika bir gün, projemiz çok güzel ilerliyor.",
        "İyi çalışmalar herkese, ekip süper.",
        "Mutlu ve verimli bir hafta.",
        "Harika sonuçlar aldık, teşekkürler.",
        "Bugün çok yorgun ve bitkin hissediyorum, stres çok yüksek.",
        "Kötü bir deneyim yaşadık, çok üzgünüm, bıktım.",
        "Hala stres ve sıkıntı devam ediyor.",
        "Toparlandık, tekrar güzel ve harika bir başlangıç.",
    ]
    # Timestamps with a silence gap between post 3 and post 4 (> 100 hours)
    post_times = [
        "2026-08-01T10:00:00Z",
        "2026-08-02T10:00:00Z",
        "2026-08-03T10:00:00Z",
        "2026-08-04T10:00:00Z",
        "2026-08-10T10:00:00Z",  # 144 hours gap!
        "2026-08-11T10:00:00Z",
        "2026-08-12T10:00:00Z",
        "2026-08-13T10:00:00Z",
    ]

    data = {
        "target_profile": {
            "posts": posts,
            "post_times": post_times,
        }
    }

    engine1 = SeismosEngine()
    engine2 = SeismosEngine()

    rep1 = await engine1.analyze(data)
    rep2 = await engine2.analyze(data)

    assert rep1.event_count == rep2.event_count
    assert rep1.event_count > 0, "At least one seismic event should be detected"
    assert rep1.max_intensity == rep2.max_intensity

    # Check that every event_id is 100% deterministic (no random UUIDs)
    ids1 = [e.event_id for e in rep1.events]
    ids2 = [e.event_id for e in rep2.events]
    assert ids1 == ids2

    # Check kind and intensities match exactly
    for e1, e2 in zip(rep1.events, rep2.events):
        assert e1.event_id == e2.event_id
        assert e1.kind == e2.kind
        assert e1.intensity == e2.intensity
        assert e1.event_id.startswith("sez_")
