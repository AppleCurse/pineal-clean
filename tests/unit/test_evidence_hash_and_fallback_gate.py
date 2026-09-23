from pydantic import BaseModel

from agent_core.services.uncertainty_engine import UncertaintyEngine
from agent_core.task_executor import PinealExecutor


class Result(BaseModel):
    value: str
    confidence: float = 0.9
    data_confidence: bool = False


def test_step_hash_is_result_sensitive_and_not_placeholder():
    assert PinealExecutor._hash_evidence_result(Result(value="a")) != PinealExecutor._hash_evidence_result(Result(value="b"))
    assert PinealExecutor._hash_evidence_result(Result(value="a")) != "HASH"


def test_unavailable_data_is_never_safe_uncertainty():
    report = UncertaintyEngine().evaluate(Result(value="fallback"), "passion_mapper")
    assert report.is_suspicious is True
    assert report.confidence == 0.0


# --------------------------------------------------------------------------- #
# [RÖNTGEN 2026-09-23 / SAHİP KARARI §8.7] Kanıt mührü TEKRAR-ÜRETİLEBİLİR
#
# Ölçülen eski kusur: `computed_at` (duvar saati) SHA-256 mühür girdisine
# giriyordu. Yani AYNI kanıt her koşuda farklı mühür üretiyordu -> mühür
# "bu koşunun mührü"ydü, kanıtın kimliği değildi; bağımsız doğrulama ve
# yeniden-üretim karşılaştırması yapılamıyordu.
# Sahip kararı: duvar saati alanları hash girdisinden ÇIKARILIR, zaman
# damgası kayıtta ayrıca taşınmaya devam eder.
# --------------------------------------------------------------------------- #
from datetime import datetime, timedelta, timezone  # noqa: E402

from agent_core.domain.pillar_models import (  # noqa: E402
    EvidenceStatus,
    PillarBundle,
    VoidReport,
    VoidSignal,
)

_T0 = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


def _bundle(when: datetime, absence: float = 0.75) -> PillarBundle:
    return PillarBundle(
        void=VoidReport(
            status=EvidenceStatus.OBSERVED,
            signals=[VoidSignal(
                topic="finans",
                category="iş",
                expected_presence=0.9,
                actual_presence=0.1,
                absence_delta=0.8,
                absence_score=absence,
                status=EvidenceStatus.OBSERVED,
                observables=["hiç paylaşım yok"],
            )],
            top_voids=["finans"],
            global_absence_index=absence,
            computed_at=when,
        ),
        computed_at=when,
    )


def test_evidence_seal_is_reproducible_across_wall_clock():
    """Aynı kanıt, farklı duvar saati -> AYNI mühür (tekrar-üretilebilirlik)."""
    first = PinealExecutor._hash_evidence_result(_bundle(_T0))
    second = PinealExecutor._hash_evidence_result(_bundle(_T0 + timedelta(hours=7, minutes=13)))
    assert first == second
    assert len(first) == 64


def test_evidence_seal_still_separates_different_evidence():
    """Tekrar-üretilebilirlik kanıtı körleştirmez: kanıt değişirse mühür değişir."""
    assert PinealExecutor._hash_evidence_result(_bundle(_T0, absence=0.75)) != \
        PinealExecutor._hash_evidence_result(_bundle(_T0, absence=0.31))


def test_wall_clock_is_stripped_only_from_seal_input_not_from_record():
    """Zaman damgası KAYBOLMAZ: kayıtta durur, yalnız mühür girdisinden çıkar."""
    bundle = _bundle(_T0)
    payload = PinealExecutor._seal_payload(bundle)

    assert bundle.computed_at == _T0, "kayıt zaman damgasını korumalı"
    assert bundle.void.computed_at == _T0
    assert "computed_at" not in payload, "kök düzeyde duvar saati mühre giremez"
    assert "computed_at" not in payload["void"], "İÇ İÇE duvar saati de mühre giremez"
    # Kanıt alanları eksiksiz kalır (mühür körleşmez):
    assert payload["void"]["signals"][0]["topic"] == "finans"
    assert payload["void"]["global_absence_index"] == 0.75
    assert payload["void"]["status"] == EvidenceStatus.OBSERVED.value or \
        payload["void"]["status"] == EvidenceStatus.OBSERVED


def test_seal_payload_survives_plain_dicts_and_non_dict_inputs():
    assert PinealExecutor._seal_payload({"value": "a", "computed_at": _T0}) == {"value": "a"}
    assert PinealExecutor._seal_payload(None) == {}
    assert PinealExecutor._seal_payload("metin") == {}
