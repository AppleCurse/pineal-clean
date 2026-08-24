"""Pineal 7-Pillar Wave-2 deterministic domain contracts."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from agent_core.domain.pillar_models import EvidenceStatus, FrequencyReport, SeismosReport, StrictModel, VoidReport


class FossilRecord(StrictModel):
    topic: str
    last_seen_iso: str
    extinction_confidence: float = Field(ge=0, le=1)
    early_presence: float = Field(ge=0, le=1, default=0)
    late_presence: float = Field(ge=0, le=1, default=0)
    observables: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class IdentityDrift(StrictModel):
    metric: str
    early_value: float
    late_value: float
    drift_ratio: float
    is_significant: bool
    observable: str = ""


class StrataReport(StrictModel):
    status: EvidenceStatus = EvidenceStatus.INSUFFICIENT_DATA
    fossils: list[FossilRecord] = Field(default_factory=list)
    drifts: list[IdentityDrift] = Field(default_factory=list)
    layer_count: int = 3
    archaeological_depth_days: float = 0
    early_range: str = ""
    late_range: str = ""
    machine_note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GravityWell(StrictModel):
    anchor: str
    mass: float = Field(ge=0)
    density: float = Field(ge=0)
    pull: float = Field(ge=0)
    recurrence: int = Field(ge=0)
    is_black_hole: bool = False
    observables: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class GravityReport(StrictModel):
    status: EvidenceStatus = EvidenceStatus.INSUFFICIENT_DATA
    wells: list[GravityWell] = Field(default_factory=list)
    dominant_attractor: str | None = None
    total_anchors_scanned: int = 0
    machine_note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BiometricSignal(StrictModel):
    signal_type: str
    label: str = ""
    value: float
    z_score: float
    baseline: float = 0
    interpretation: str = ""


class PulseReport(StrictModel):
    status: EvidenceStatus = EvidenceStatus.INSUFFICIENT_DATA
    signals: list[BiometricSignal] = Field(default_factory=list)
    baseline_volatility: float = 0
    rhythm_signature: str = ""
    machine_note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResonanceVector(StrictModel):
    dimension: str
    approach: str
    avoid: str
    confidence: float = Field(ge=0, le=1)
    source_pillars: list[str] = Field(default_factory=list)


class KeyReport(StrictModel):
    status: EvidenceStatus = EvidenceStatus.INSUFFICIENT_DATA
    frequency_signature: str = ""
    core_tension: str = ""
    gate_key: str = ""
    walls: list[str] = Field(default_factory=list)
    rhythm_note: str = ""
    channel_recommendation: str = ""
    timing_window: str = ""
    vectors: list[ResonanceVector] = Field(default_factory=list)
    pillar_summary: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1, default=0)
    machine_note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FullPillarBundle(StrictModel):
    frequency: FrequencyReport = Field(default_factory=FrequencyReport)
    seismos: SeismosReport = Field(default_factory=SeismosReport)
    void: VoidReport = Field(default_factory=VoidReport)
    strata: StrataReport = Field(default_factory=StrataReport)
    gravity: GravityReport = Field(default_factory=GravityReport)
    pulse: PulseReport = Field(default_factory=PulseReport)
    key: KeyReport = Field(default_factory=KeyReport)
    version: Literal["pillar-full-v1"] = "pillar-full-v1"
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def as_snapshot_fields(self) -> dict[str, Any]:
        return {
            "frequency_map": self.frequency.model_dump(mode="json"),
            "seismos_events": self.seismos.model_dump(mode="json"),
            "void_map": self.void.model_dump(mode="json"),
            "strata_map": self.strata.model_dump(mode="json"),
            "gravity_map": self.gravity.model_dump(mode="json"),
            "pulse_map": self.pulse.model_dump(mode="json"),
            "key_matrix": self.key.model_dump(mode="json"),
            "pillar_bundle": self.model_dump(mode="json"),
        }
