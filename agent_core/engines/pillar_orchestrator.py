"""Two-phase asynchronous 7-Pillar orchestrator."""

import asyncio
import logging

from agent_core.domain.pillar_models import FrequencyReport, SeismosReport, VoidReport
from agent_core.domain.pillar_wave2_models import FullPillarBundle, GravityReport, KeyReport, PulseReport, StrataReport

from .frequency_engine import FrequencyEngine
from .gravity_engine import GravityEngine
from .key_engine import KeyEngine
from .pulse_engine import PulseEngine
from .seismos_engine import SeismosEngine
from .strata_engine import StrataEngine
from .void_engine import VoidEngine

logger = logging.getLogger(__name__)


class PillarOrchestrator:
    def __init__(self, frequency=None, seismos=None, void=None, strata=None, gravity=None, pulse=None, key=None):
        self.frequency = frequency or FrequencyEngine()
        self.seismos = seismos or SeismosEngine()
        self.void = void or VoidEngine()
        self.strata = strata or StrataEngine()
        self.gravity = gravity or GravityEngine()
        self.pulse = pulse or PulseEngine()
        self.key = key or KeyEngine()

    async def run(self, data):
        specs = [
            (self.frequency, FrequencyReport, "FREQUENCY"),
            (self.seismos, SeismosReport, "SEISMOS"),
            (self.void, VoidReport, "VOID"),
            (self.strata, StrataReport, "STRATA"),
            (self.gravity, GravityReport, "GRAVITY"),
            (self.pulse, PulseReport, "PULSE"),
        ]

        async def safe(engine, model, name):
            try:
                return await engine.analyze(data)
            except Exception as e:
                logger.warning("%s error: %s", name, e)
                return model(machine_note=f"{name} error: {type(e).__name__}: {str(e)[:120]}")

        f, s, v, st, g, p = await asyncio.gather(*(safe(*x) for x in specs))
        try:
            k = await self.key.analyze(freq=f, seismos=s, void=v, strata=st, gravity=g, pulse=p)
        except Exception as e:
            k = KeyReport(machine_note=f"KEY error: {type(e).__name__}: {str(e)[:120]}")
        return FullPillarBundle(
            frequency=f, seismos=s, void=v, strata=st, gravity=g, pulse=p, key=k
        ).as_snapshot_fields()
