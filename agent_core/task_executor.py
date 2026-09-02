import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List

from datetime import datetime, timezone
from pydantic import BaseModel

from agent_core.agents.authenticity_auditor import AuthenticityAuditorAgent
from agent_core.agents.autonomous_verifier import AutonomousVerifier
from agent_core.agents.cognitive_profiler import CognitiveProfilerAgent
from agent_core.agents.depth_analyst import DepthAnalyst
from agent_core.agents.friction_detector import FrictionDetectorAgent
from agent_core.agents.human_behavior import HumanBehaviorAnalyzer
from agent_core.agents.interpreter_agent import InterpreterAgent
from agent_core.agents.mirror_truth import MirrorOfTruth
from agent_core.agents.osint_investigator import OsintInvestigatorAgent
from agent_core.agents.passion_mapper import PassionMapperAgent
from agent_core.agents.pattern_interrupt import PatternInterrupt
from agent_core.agents.resonance_calculator import ResonanceCalculator
from agent_core.agents.resonance_synthesizer import ResonanceSynthesizerAgent
from agent_core.domain.memory_models import (
    AgentRun,
    AuthenticBridge,
    CognitiveStyle,
    FrictionProfile,
    HolisticProfile,
    PassionProfile,
    TaskSnapshot,
)
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.config_loader import DecisionConfig
from agent_core.services.canonical_memory import MemoryCorruptedError, MemoryState
from agent_core.services.cognitive_router import CognitiveRouter, RoutePlan
from agent_core.services.decision_engine import DecisionEngine
from agent_core.services.hindsight_memory import build_memory_from_env
from agent_core.services.llm_gateway import LLMGateway
from agent_core.services.memory_injector import MemoryInjector
from agent_core.services.search_engine import SearchEngine
from agent_core.services.uncertainty_engine import UncertaintyEngine
from agent_core.services.vision_analyzer import VisionAnalyzer
from agent_core.shadow.shadow_executor import ShadowExecutor

class InsufficientEvidenceError(RuntimeError):
    pass

class VerifiedNote(BaseModel):
    note: str

class TaskStatus(TaskSnapshot):
    pass


class PinealExecutor:
    def __init__(self, log_callback=None, emit_event_callback=None, snapshot_callback=None):
        self._log = log_callback or (lambda level, msg: None)
        self._emit = emit_event_callback or (lambda evt: None)
        self._snapshot_cb = snapshot_callback
        self.router = CognitiveRouter()
        self.memory = build_memory_from_env()
        self.injector = MemoryInjector()
        self.config = DecisionConfig.load()
        self.decision_engine = DecisionEngine(self.config)
        self.uncertainty = UncertaintyEngine()
        self.llm_gateway = LLMGateway()
        self.search_engine = SearchEngine()
        self.vision_analyzer = VisionAnalyzer(self.llm_gateway)
        self.agents = {
            "passion_mapper": PassionMapperAgent(self.llm_gateway),
            "friction_detector": FrictionDetectorAgent(self.llm_gateway),
            "cognitive_profiler": CognitiveProfilerAgent(self.llm_gateway),
            "resonance_synthesizer": ResonanceSynthesizerAgent(self.llm_gateway),
            "human_behavior": HumanBehaviorAnalyzer(),
            "mirror_truth": MirrorOfTruth(self.llm_gateway),
            "resonance_calc": ResonanceCalculator(),
            "pattern_interrupt": PatternInterrupt(),
            "autonomous_verifier": AutonomousVerifier(self.search_engine),
            "authenticity_auditor": AuthenticityAuditorAgent(self.llm_gateway),
            "osint_investigator": OsintInvestigatorAgent(self.llm_gateway),
            "shadow_executor": ShadowExecutor(llm_gateway=self.llm_gateway),
            "depth_analyst": DepthAnalyst(self.llm_gateway),
        }
        # [SEC FIX] Interpreter (Open Interpreter kod-icra yığını) varsayılan
        # registry'de YOKTUR; yalnızca açıkça ENABLE_INTERPRETER=true ile
        # yüklenir. Ana pipeline rotası da bu ajanı artık planlamaz
        # (cognitive_router). /api/experimental/interpreter/execute zaten
        # aynı env kapısıyla varsayılan 403 döner.
        import os as _os
        if _os.getenv("ENABLE_INTERPRETER", "false").lower() == "true":
            self.agents["interpreter"] = InterpreterAgent(self.llm_gateway)

    @staticmethod
    def _hash_evidence_result(result: BaseModel) -> str:
        """Canonical SHA-256 hash for a single typed agent result."""
        import hashlib
        import json
        canonical = json.dumps(result.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # LLM çağrısı yapmayan tamamen deterministik ajanlar. Bu listede olmayan
    # bir ajanın sonucu data_confidence ile kanıtlanmıyorsa UI'da "LLM"
    # rozeti gösterilemez; "kaynak belirsiz" olarak işaretlenir.
    _DETERMINISTIC_AGENTS = frozenset({"resonance_calc"})

    @contextmanager
    def _capture_llm_calls(self, task_id: str, agent_id: str) -> Iterator[Any]:
        """Use gateway task-local capture, with a no-op scope for test doubles."""
        capture = getattr(type(self.llm_gateway), "capture_calls", None)
        if callable(capture):
            with capture(self.llm_gateway, task_id, agent_id) as scope:
                yield scope
            return
        yield SimpleNamespace(records=[], call_ids=[])

    def _provenance_for(
        self,
        agent_name: str,
        result: Any,
        call_records: list[dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Build output provenance only from records captured for this agent."""
        records = list(call_records or [])
        call_ids = [record["call_id"] for record in records if record.get("call_id")]
        fallback = getattr(result, "fallback_reason", None)
        data_confidence = getattr(result, "data_confidence", True)

        if data_confidence is False or fallback:
            return {
                "source": "fallback",
                "fallback_reason": fallback or "low_confidence",
                "call_ids": call_ids,
                "call_id": None,
                "model": None,
                "provider": None,
            }
        if agent_name in self._DETERMINISTIC_AGENTS:
            return {
                "source": "deterministic",
                "fallback_reason": None,
                "call_ids": call_ids,
                "call_id": None,
                "model": None,
                "provider": None,
            }

        successful = [record for record in records if not record.get("error")]
        if successful:
            selected = successful[-1]
            return {
                "source": "llm_cache" if selected.get("cache_hit") else "llm",
                "fallback_reason": None,
                "call_ids": call_ids,
                "call_id": selected.get("call_id"),
                "model": selected.get("model"),
                "provider": selected.get("provider"),
            }
        if records:
            selected = records[-1]
            return {
                "source": "llm_error",
                "fallback_reason": selected.get("error") or "llm_call_failed",
                "call_ids": call_ids,
                "call_id": selected.get("call_id"),
                "model": selected.get("model"),
                "provider": selected.get("provider"),
            }
        return {
            "source": "unknown",
            "fallback_reason": "no_llm_trace",
            "call_ids": [],
            "call_id": None,
            "model": None,
            "provider": None,
        }

    def _snapshot(self, status: TaskStatus):
        cache_stats = self.llm_gateway.cache.stats() if hasattr(self.llm_gateway, "cache") else {}
        hits = cache_stats.get("hits", 0)
        hit_rate = cache_stats.get("hit_rate", "0.0%")

        budget_reader = getattr(type(self.llm_gateway), "budget_status", None)
        budget = budget_reader(self.llm_gateway) if callable(budget_reader) else {}
        real_cost = budget.get("spend_usd", getattr(self.llm_gateway, "spend_usd", None))
        if not isinstance(real_cost, (int, float)):
            real_cost = getattr(self.llm_gateway, "total_cost", 0.0)
        if not isinstance(real_cost, (int, float)):
            real_cost = 0.0
        reserved_cost = budget.get("reserved_usd", 0.0)
        active_reservations = budget.get("active_reservations", 0)

        # [034] fix: telemetri yalnızca GERÇEK gözlemlenebilirlerden oluşur.
        # - 'saved_llm_cost' varsayımsal $0.005/call sabitiyle uyduruluyordu;
        #   cache hit'leri model/fiyat bilgisi taşımadığı için kesin tasarruf
        #   hesaplanamaz -> hit sayısı dürüstçe raporlanır.
        # - 'decision_weight_updates' hiçbir ağırlık güncellemesi yapılmayan
        #   yolda ajan sayısını yanlış etiketliyordu -> gerçek LLM çağrı
        #   gözlem sayısı raporlanır (gateway call_log).
        call_log = getattr(self.llm_gateway, "call_log", None)
        memory_telemetry = {}
        memory_inspector = getattr(type(self.memory), "inspect_task_memory", None)
        if callable(memory_inspector):
            inspection = memory_inspector(self.memory, status.task_id)
            memory_telemetry["memory_state"] = inspection.get("state")
            if inspection.get("error_code"):
                memory_telemetry["memory_error_code"] = inspection["error_code"]

        status.telemetry = {
            **(status.telemetry or {}),
            **memory_telemetry,
            "cache_hit_rate": hit_rate,
            "cache_hits": hits if isinstance(hits, (int, float)) else 0,
            "llm_calls_observed": len(call_log) if isinstance(call_log, list) else 0,
            "total_llm_cost": f"${real_cost:.5f}",
            "llm_spend_usd": real_cost,
            "llm_reserved_spend_usd": reserved_cost,
            "llm_active_reservations": active_reservations,
        }
        
        if self._snapshot_cb:
            self._snapshot_cb(status)
            
    def _summarize_input(self, input_data: dict, agent_name: str) -> dict:
        profile = input_data.get("target_profile", {})
        return {
            "bio_len": len(profile.get("bio", "")),
            "post_count": len(profile.get("posts", [])),
            "has_images": bool(profile.get("images")),
            "has_mirror": "user_mirror" in input_data,
            "has_target_analysis": "target_analysis" in input_data,
        }

    async def _download_images(self, urls: List[str]) -> List[str]:
        import httpx
        import asyncio

        def _write_file(content):
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp.write(content)
            tmp.close()
            return tmp.name

        async def fetch_image(c, u):
            from agent_core.utils.security import safe_get

            try:
                r = await safe_get(c, u, max_redirects=3)
                r.raise_for_status()
                if len(r.content) > 8 * 1024 * 1024:
                    raise ValueError("IMAGE_TOO_LARGE")
                # Offload synchronous file I/O to a thread to avoid blocking the event loop
                return await asyncio.to_thread(_write_file, r.content)
            except Exception as e:
                self._log("WARNING", "Gorsel indirilemedi: " + type(e).__name__)
                return None

        # Use a shared httpx.AsyncClient to enable connection pooling
        async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
            results = await asyncio.gather(*(fetch_image(client, u) for u in urls[:2]))
        
        paths = [p for p in results if p is not None]
        return paths

    async def _deep_research(self, original_result: BaseModel, check, agent_name: str) -> VerifiedNote:
        """Request a separate review without changing the originating agent output."""
        prompt = (
            f"{agent_name} ajaninin onceki analizi supheli bulundu.\n"
            f"Suphe nedeni: {check.reason}\n"
            "Orijinal ajan ciktisi (degistirilemez kayit): " + original_result.model_dump_json() +
            "\nKurallar: 1) Emin degilsen 'bilmiyorum' de 2) Tahmin uretme "
            "3) Sadece verilen veriyi degerlendir 4) Orijinal analizi yeniden yazma; "
            "yalnizca dogrulama/degerlendirme notu ver."
        )
        verified = await self.llm_gateway.query(prompt, temperature=0.1, tier=1)
        return VerifiedNote(note=verified)

    @staticmethod
    def _evidence_record(agent_name: str, result: BaseModel, *, evidence_type: str,
                         uncertainty=None, source_agent: str | None = None,
                         llm_calls: list | None = None) -> dict:
        """Build an auditable evidence entry while retaining its provenance."""
        record = {
            "agent": agent_name,
            "result": result.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evidence_type": evidence_type,
        }
        if source_agent is not None:
            record["source_agent"] = source_agent
        if uncertainty is not None:
            record["uncertainty"] = uncertainty.model_dump()
        if llm_calls is not None:
            # Records were captured in this agent's context-local scope. They
            # are already plain dictionaries and remain JSON serializable.
            record["call_ids"] = [call["call_id"] for call in llm_calls if call.get("call_id")]
            record["llm_calls"] = [call.copy() for call in llm_calls]
        return record

    async def execute_task(self, input_data: Dict[str, Any], task_id: str) -> TaskStatus:
        """Public entry: impl'i saran güvenli yaşam döngüsü.

        [035] fix: göreve ait geçici görseller başarı/halt/exception HER
        durumunda temizlenir; hedefin kişisel görselleri temp dizinde kalıcı
        artefakt olarak bırakılamaz (retention sözleşmesi).
        """
        try:
            return await self._execute_task_impl(input_data, task_id)
        except MemoryCorruptedError as exc:
            # A corrupt canonical record is not equivalent to an absent record.
            # Halt before further analysis and require explicit recovery.
            from agent_core.schemas.telemetry import ErrorHaltEvent, Severity

            now = datetime.now(timezone.utc)
            status = TaskStatus(
                task_id=task_id,
                status=PipelineStatus.HALTED_CRITICAL,
                created_at=now,
                completed_at=now,
                halted_reason=exc.error_code,
                telemetry={
                    "memory_initial_state": MemoryState.CORRUPTED.value,
                    "memory_state": MemoryState.CORRUPTED.value,
                    "memory_error_code": exc.error_code,
                    "memory_corruption_reason": exc.reason,
                },
            )
            self._log("ERROR", f"[{task_id}] {exc}")
            self._emit(ErrorHaltEvent(
                task_id=task_id,
                agent_name="CanonicalMemory",
                error_code=exc.error_code,
                error_message=f"Canonical memory requires explicit recovery ({exc.reason})",
                severity=Severity.Critical,
            ))
            self._snapshot(status)
            return status
        finally:
            self._cleanup_temp_images(input_data)

    def _cleanup_temp_images(self, input_data: Dict[str, Any]) -> None:
        import os
        for path in (input_data.pop("_downloaded_temp_images", None) or []):
            try:
                os.remove(path)
            except OSError:
                pass

    async def _execute_task_impl(self, input_data: Dict[str, Any], task_id: str) -> TaskStatus:
        from agent_core.schemas.telemetry import (
            TaskStartedEvent, StepCompletedEvent, ErrorHaltEvent, TaskCompletedEvent, Severity
        )
        status = TaskStatus(task_id=task_id, status="processing", created_at=datetime.now(timezone.utc))
        _task_wall_start = datetime.now(timezone.utc)

        # Only concrete memory engines participate in the health contract; test
        # doubles without the method retain their existing behavior.
        inspector = getattr(type(self.memory), "inspect_task_memory", None)
        if callable(inspector):
            memory_inspection = inspector(self.memory, task_id)
            memory_state = memory_inspection.get("state", MemoryState.CORRUPTED.value)
            status.telemetry = {
                "memory_initial_state": memory_state,
                "memory_state": memory_state,
            }
            if memory_state == MemoryState.CORRUPTED.value:
                profile_file = self.memory._profile_file(task_id)
                raise MemoryCorruptedError(
                    task_id,
                    memory_inspection.get("reason") or "UNKNOWN",
                    profile_file,
                )

        input_data["sacred_rules"] = self.injector.fetch_active_rules()
        # The shared diagnostic call log is intentionally not cleared here.
        # Concurrent tasks bind records through per-agent context-local scopes.

        # Deterministik Takipçi ve Zamanlama Forensiği
        try:
            from agent_core.services.follower_audit import audit_followers
            from agent_core.services.timing_forensics import analyze_timing
            tp_info = input_data.get("target_profile", {})
            fol_cnt = tp_info.get("followers", 0)
            # [024] fix: following=None "ölçülmedi" demektir; 0'a çevrilmez.
            fing_cnt = tp_info.get("following")
            # [027] fix: sahte 1-post sentinel'i kaldırıldı. Boş posts_meta
            # olduğu gibi iletilir; audit "İncelenen Post: 0" der, 1 demez.
            posts_meta = tp_info.get("posts_meta") or []
            audit_res = audit_followers(fol_cnt, fing_cnt, posts_meta)
            input_data["follower_audit"] = audit_res.model_dump()
            status.follower_audit = audit_res.model_dump()
            self._log("INFO", f"[{task_id}] TAKİPÇİ DENETİMİ: {audit_res.verdict.upper()}")
            
            p_times = tp_info.get("post_times", [])
            t_res = analyze_timing(p_times)
            if t_res:
                input_data["timing_forensics"] = t_res
                status.timing_forensics = t_res
                # W1: timing_forensics'in GERCEK alanlari (night_share, peak_hour,
                # median_drift_hours) okunur; olmayan alanlarla %0 gosterilmez.
                gece = int(t_res.get("night_share", 0) * 100)
                tepe = str(t_res.get("peak_hour", "--"))
                kayma = t_res.get("median_drift_hours", 0)
                kayma_str = f"+{kayma:.1f}sa" if kayma >= 0 else f"{kayma:.1f}sa"
                self._log("INFO", f"[{task_id}] ZAMAN FORENSİĞİ: gece %{gece} | tepe {tepe} | kayma {kayma_str}")
        except Exception as e:
            self._log("WARNING", f"[{task_id}] Forensik veri analizi uyarısı: {e}")

        raw_imgs = input_data.get("target_profile", {}).get("images", [])
        if raw_imgs and isinstance(raw_imgs, list) and len(raw_imgs) > 0 and isinstance(raw_imgs[0], str) and raw_imgs[0].startswith("http"):
            self._log("INFO", f"[{task_id}] MULTIMODAL VISION: {len(raw_imgs)} fotoğraf görsel zeka ile inceleniyor...")
            try:
                target_bio = input_data.get("target_profile", {}).get("bio", "")
                with self._capture_llm_calls(task_id, "vision_analyzer") as vision_scope:
                    visual_ev = await self.vision_analyzer.analyze_images(raw_imgs, target_context=target_bio)
                input_data["visual_evidence"] = visual_ev.model_dump()
                status.visual_evidence = visual_ev.model_dump()
                status.visual_evidence["_provenance"] = self._provenance_for(
                    "vision_analyzer", visual_ev, vision_scope.records
                )
                self._log("INFO", f"[{task_id}] GÖRSEL KANIT: {visual_ev.visual_evidence_summary}")
            except Exception as e:
                self._log("WARNING", f"[{task_id}] Vision analizi atlandı: {str(e)[:80]}")

        imgs = input_data.get("target_profile", {}).get("images", [])
        if imgs and isinstance(imgs[0], str) and imgs[0].startswith("http"):
            downloaded = await self._download_images(imgs)
            input_data["target_profile"]["images"] = downloaded
            # [035] fix: task bitince (her çıkış yolunda) silinecekleri kaydet.
            input_data["_downloaded_temp_images"] = downloaded

        # --- PINEAL DETERMINISTIC 7-PILLAR ---
        pillar_start = datetime.now(timezone.utc)
        self._log("INFO", f"[{task_id}] 7-PILLAR analizi başlatılıyor...")
        try:
            from agent_core.engines.pillar_orchestrator import PillarOrchestrator

            pillar_fields = await PillarOrchestrator().run(input_data)
            for field in (
                "frequency_map", "seismos_events", "void_map", "strata_map",
                "gravity_map", "pulse_map", "key_matrix", "pillar_bundle",
            ):
                setattr(status, field, pillar_fields.get(field))
            input_data["pillar_bundle"] = pillar_fields.get("pillar_bundle")
            pillar_end = datetime.now(timezone.utc)
            elapsed_ms = int((pillar_end - pillar_start).total_seconds() * 1000)
            status.evidence_chain.append({
                "agent": "pineal_7pillar",
                "result": {
                    "frequency": (status.frequency_map or {}).get("status"),
                    "seismos_events": (status.seismos_events or {}).get("event_count", 0),
                    "void_top": (status.void_map or {}).get("top_voids", []),
                    "gravity_dominant": (status.gravity_map or {}).get("dominant_attractor"),
                    "pulse_rhythm": (status.pulse_map or {}).get("rhythm_signature"),
                    "key_confidence": (status.key_matrix or {}).get("confidence", 0),
                    "elapsed_ms": elapsed_ms,
                },
                "timestamp": pillar_end.isoformat(),
            })
            status.agent_runs["pineal_7pillar"] = AgentRun(
                task_id=task_id, agent_name="pineal_7pillar", status="completed",
                started_at=pillar_start, completed_at=pillar_end,
                confidence=(status.key_matrix or {}).get("confidence", 0),
                output_summary={
                    name: (pillar_fields.get(field) or {}).get("machine_note", "")
                    for name, field in (
                        ("frequency", "frequency_map"), ("seismos", "seismos_events"),
                        ("void", "void_map"), ("strata", "strata_map"),
                        ("gravity", "gravity_map"), ("pulse", "pulse_map"),
                        ("key", "key_matrix"),
                    )
                },
            )
            self._log("INFO", f"[{task_id}] 7-PILLAR tamamlandı ({elapsed_ms}ms)")
            self._snapshot(status)
        except Exception as e:
            error_time = datetime.now(timezone.utc)
            error_code = type(e).__name__
            self._log("ERROR", f"[{task_id}] 7-PILLAR failure: {error_code}: {e}")
            status.agent_runs["pineal_7pillar"] = AgentRun(
                task_id=task_id, agent_name="pineal_7pillar", status="failed",
                started_at=pillar_start, completed_at=error_time,
                error_code=error_code,
                error_message=str(e)[:250],
            )
            # Failures are evidence too: retain a serializable record instead
            # of leaving an unexplained gap in the chain.
            status.evidence_chain.append({
                "agent": "pineal_7pillar",
                "evidence_type": "execution_failure",
                "result": {"error_code": error_code, "error_message": str(e)[:250]},
                "timestamp": error_time.isoformat(),
            })
            pillar_cfg = self.config.get_agent_config("pineal_7pillar")
            if not pillar_cfg.graceful_degradation:
                status.status = PipelineStatus.HALTED_CRITICAL
                status.halted_reason = "7-pillar evidence foundation failed"
                status.completed_at = error_time
                self._emit(ErrorHaltEvent(
                    task_id=task_id,
                    agent_name="pineal_7pillar",
                    error_code=error_code,
                    error_message=str(e)[:200],
                    severity=Severity.Critical,
                ))
                await self.memory.merge_evidence(task_id, status.evidence_chain)
                self._snapshot(status)
                return status
            self._snapshot(status)

        self._emit(TaskStartedEvent(
            task_id=task_id,
            agent_name="PinealExecutor",
            input_summary="Profil verisi işleniyor, ajan rotası çiziliyor."
        ))

        route: RoutePlan = await self.router.analyze(input_data)
        self._log("INFO", "[" + task_id + "] ROUTE: " + " -> ".join(route.agents))
        status.planned_agents = route.agents.copy()
        self._snapshot(status)
        
        deferred = []
        try:
            for agent_name in route.agents:
                if agent_name in ["pattern_interrupt", "resonance_synthesizer"]:
                    deferred.append(agent_name)
                    continue
                if agent_name not in self.agents:
                    raise KeyError("Bilinmeyen yetenek: " + agent_name)
                status.current_agent = agent_name
                self._log("WARNING", "[" + task_id + "] AGENT " + agent_name + ": calisiyor")
                
                run = AgentRun(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    input_summary=self._summarize_input(input_data, agent_name),
                )
                status.agent_runs[agent_name] = run
                self._snapshot(status)
                
                self._emit(TaskStartedEvent(
                    task_id=task_id,
                    agent_name=agent_name,
                    input_summary="Ajan tetiklendi"
                ))
                agent_cfg = self.config.get_agent_config(agent_name)
                
                agent_llm_calls: list[dict[str, Any]] = []
                try:
                    agent = self.agents[agent_name]
                    with self._capture_llm_calls(task_id, agent_name) as agent_scope:
                        try:
                            try:
                                result = await agent.execute(input_data, self.memory, self.llm_gateway)
                            except TypeError:
                                result = await agent.execute(input_data)
                        finally:
                            agent_llm_calls = list(agent_scope.records)
                            run.call_ids = list(agent_scope.call_ids)
                    if not isinstance(result, BaseModel):
                        raise TypeError(agent_name + " gecersiz cikti: " + str(type(result)))
                except InsufficientEvidenceError:
                    raise
                except Exception as e:
                    run.status = "failed"
                    run.error_code = type(e).__name__
                    run.error_message = str(e)[:200]
                    self._log("ERROR", f"[{task_id}] AGENT {agent_name} BASTARISIZ: {type(e).__name__}: {str(e)[:200]}")
                    
                    if agent_name in self.config.critical_agents or not agent_cfg.graceful_degradation:
                        status.status = "halted_critical"
                        status.completed_at = datetime.now(timezone.utc)
                        self._snapshot(status)
                        self._emit(ErrorHaltEvent(
                            task_id=task_id,
                            agent_name=agent_name,
                            error_code=type(e).__name__,
                            error_message=str(e)[:200],
                            severity=Severity.Critical
                        ))
                        self._log("ERROR", f"[{task_id}] PIPELINE FAILED; critical agent failed.")
                        await self.memory.merge_evidence(task_id, status.evidence_chain)
                        return status
                    else:
                        self._log("WARNING", f"[{task_id}] Non-critical agent {agent_name} failed. Continuing pipeline (graceful degradation).")
                        self._snapshot(status)
                        continue

                check = self.uncertainty.evaluate(result, agent_name)
                
                if check.confidence < agent_cfg.min_llm_confidence:
                    halt_reason = check.reason
                    self._log("ERROR", f"[{task_id}] COGNITIVE ROUTER: {halt_reason}")
                    run.status = "halted"
                    run.error_code = "LOW_CONFIDENCE"
                    run.error_message = halt_reason
                    
                    if agent_name in self.config.critical_agents or not agent_cfg.graceful_degradation:
                        status.halted_reason = halt_reason
                        status.status = "halted_critical"
                        self._snapshot(status)
                        raise InsufficientEvidenceError(halt_reason)
                    else:
                        self._log("WARNING", f"[{task_id}] Non-critical agent {agent_name} halted due to evidence. Continuing pipeline.")
                        self._snapshot(status)
                        continue

                research_note = None
                _deep_llm_calls: list[dict[str, Any]] = []
                if check.is_suspicious:
                    self._log("ERROR", "[" + task_id + "] UNCERTAINTY: " + check.reason)
                    try:
                        # Preserve `result`: downstream dependencies must receive the
                        # actual typed agent output, never a generic research note.
                        with self._capture_llm_calls(task_id, "deep_research") as research_scope:
                            try:
                                research_note = await self._deep_research(result, check, agent_name)
                            finally:
                                _deep_llm_calls = list(research_scope.records)
                    except Exception as e:
                        if agent_name in self.config.critical_agents or not agent_cfg.graceful_degradation:
                            raise InsufficientEvidenceError("Supheli kanit dogrulanamadi: " + str(e)[:80])
                        else:
                            self._log("WARNING", f"[{task_id}] Non-critical agent {agent_name} deep research failed. Continuing.")
                            continue

                if agent_name == "mirror_truth":
                    input_data["user_mirror"] = result.model_dump()
                    user_vector = await self._calculate_authentic_vector(input_data["user_mirror"])
                    self._store_authentic_vector(input_data, "user", user_vector)
                elif agent_name == "human_behavior":
                    input_data["target_analysis"] = result.model_dump()
                    target_vector = await self._calculate_authentic_vector(input_data["target_analysis"])
                    self._store_authentic_vector(input_data, "target", target_vector)
                elif agent_name == "passion_mapper":
                    input_data["passions"] = result.model_dump()
                elif agent_name == "friction_detector":
                    input_data["frictions"] = result.model_dump()
                elif agent_name == "cognitive_profiler":
                    input_data["cognitive"] = result.model_dump()
                elif agent_name == "autonomous_verifier":
                    input_data["verifications"] = result.model_dump()

                status.evidence_chain.append(self._evidence_record(
                    agent_name,
                    result,
                    evidence_type="agent_output",
                    uncertainty=check,
                    llm_calls=agent_llm_calls,
                ))
                if research_note is not None:
                    status.evidence_chain.append(self._evidence_record(
                        "deep_research",
                        research_note,
                        evidence_type="verification_note",
                        source_agent=agent_name,
                        uncertainty=check,
                        llm_calls=_deep_llm_calls,
                    ))

                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.output_summary = result.model_dump()
                run.output_summary["_provenance"] = self._provenance_for(agent_name, result, agent_llm_calls)
                run.confidence = round(check.confidence, 3)
                if agent_name not in status.completed_agents:
                    status.completed_agents.append(agent_name)
                
                if agent_name == "resonance_calc":
                    status.resonance_score = getattr(result, "compatibility_score", None)
                self._snapshot(status)
                
                self._emit(StepCompletedEvent(
                    task_id=task_id,
                    agent_name=agent_name,
                    step_name="execute",
                    output_hash=self._hash_evidence_result(result)
                ))

                if agent_name == "resonance_calc" and hasattr(result, "compatibility_score") and result.compatibility_score < 0.70:
                    self._log("ERROR", "[" + task_id + "] FREKANS UYUSMAZLIGI: " + str(round(result.compatibility_score, 2)))
                    status.status = "halted_frequency"
                    status.halted_reason = "Frekans uyusmazligi"
                    status.completed_at = datetime.now(timezone.utc)
                    await self.memory.merge_evidence(task_id, status.evidence_chain)
                    self._snapshot(status)
                    return status

            # Deferred agents run after their dependencies, not outside the
            # evidence contract.  Ordering must never bypass validation,
            # uncertainty thresholds, or graceful-degradation policy.
            for agent_name in deferred:
                if agent_name not in self.agents:
                    raise KeyError("Bilinmeyen yetenek: " + agent_name)
                status.current_agent = agent_name
                self._log("WARNING", "[" + task_id + "] AGENT " + agent_name + ": calisiyor")
                run = AgentRun(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    input_summary=self._summarize_input(input_data, agent_name),
                )
                status.agent_runs[agent_name] = run
                self._snapshot(status)
                self._emit(TaskStartedEvent(
                    task_id=task_id,
                    agent_name=agent_name,
                    input_summary="Ajan tetiklendi",
                ))
                agent_cfg = self.config.get_agent_config(agent_name)

                agent_llm_calls: list[dict[str, Any]] = []
                try:
                    agent = self.agents[agent_name]
                    with self._capture_llm_calls(task_id, agent_name) as agent_scope:
                        try:
                            try:
                                result = await agent.execute(input_data, self.memory, self.llm_gateway)
                            except TypeError:
                                result = await agent.execute(input_data)
                        finally:
                            agent_llm_calls = list(agent_scope.records)
                            run.call_ids = list(agent_scope.call_ids)
                    if not isinstance(result, BaseModel):
                        raise TypeError(agent_name + " gecersiz cikti: " + str(type(result)))
                except InsufficientEvidenceError:
                    raise
                except Exception as e:
                    run.status = "failed"
                    run.error_code = type(e).__name__
                    run.error_message = str(e)[:200]
                    self._log("ERROR", f"[{task_id}] AGENT {agent_name} BASTARISIZ: {type(e).__name__}: {str(e)[:200]}")
                    if agent_name in self.config.critical_agents or not agent_cfg.graceful_degradation:
                        status.status = "halted_critical"
                        status.completed_at = datetime.now(timezone.utc)
                        self._snapshot(status)
                        self._emit(ErrorHaltEvent(
                            task_id=task_id,
                            agent_name=agent_name,
                            error_code=type(e).__name__,
                            error_message=str(e)[:200],
                            severity=Severity.Critical,
                        ))
                        await self.memory.merge_evidence(task_id, status.evidence_chain)
                        return status
                    self._log("WARNING", f"[{task_id}] Non-critical deferred agent {agent_name} failed. Continuing pipeline.")
                    self._snapshot(status)
                    continue

                check = self.uncertainty.evaluate(result, agent_name)
                if check.confidence < agent_cfg.min_llm_confidence:
                    halt_reason = check.reason
                    run.status = "halted"
                    run.error_code = "LOW_CONFIDENCE"
                    run.error_message = halt_reason
                    self._log("ERROR", f"[{task_id}] COGNITIVE ROUTER: {halt_reason}")
                    if agent_name in self.config.critical_agents or not agent_cfg.graceful_degradation:
                        status.halted_reason = halt_reason
                        status.status = "halted_critical"
                        self._snapshot(status)
                        raise InsufficientEvidenceError(halt_reason)
                    self._log("WARNING", f"[{task_id}] Non-critical deferred agent {agent_name} halted due to evidence.")
                    self._snapshot(status)
                    continue

                research_note = None
                _deep_llm_calls: list[dict[str, Any]] = []
                if check.is_suspicious:
                    self._log("ERROR", "[" + task_id + "] UNCERTAINTY: " + check.reason)
                    try:
                        with self._capture_llm_calls(task_id, "deep_research") as research_scope:
                            try:
                                research_note = await self._deep_research(result, check, agent_name)
                            finally:
                                _deep_llm_calls = list(research_scope.records)
                    except Exception as e:
                        if agent_name in self.config.critical_agents or not agent_cfg.graceful_degradation:
                            raise InsufficientEvidenceError("Supheli kanit dogrulanamadi: " + str(e)[:80])
                        run.status = "halted"
                        run.error_code = "SUSPICIOUS_EVIDENCE"
                        run.error_message = str(e)[:200]
                        self._log("WARNING", f"[{task_id}] Non-critical deferred agent {agent_name} deep research failed.")
                        self._snapshot(status)
                        continue

                status.evidence_chain.append(self._evidence_record(
                    agent_name,
                    result,
                    evidence_type="agent_output",
                    uncertainty=check,
                    llm_calls=agent_llm_calls,
                ))
                if research_note is not None:
                    status.evidence_chain.append(self._evidence_record(
                        "deep_research",
                        research_note,
                        evidence_type="verification_note",
                        source_agent=agent_name,
                        uncertainty=check,
                        llm_calls=_deep_llm_calls,
                    ))
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.output_summary = result.model_dump()
                run.output_summary["_provenance"] = self._provenance_for(agent_name, result, agent_llm_calls)
                run.confidence = round(check.confidence, 3)
                if agent_name not in status.completed_agents:
                    status.completed_agents.append(agent_name)
                self._snapshot(status)
                self._emit(StepCompletedEvent(
                    task_id=task_id,
                    agent_name=agent_name,
                    step_name="execute",
                    output_hash=self._hash_evidence_result(result),
                ))

            # --- 360° HOLISTIC PROFILE OLUŞTURMA ---
            passions_obj = None
            frictions_obj = None
            cognitive_obj = None
            bridge_obj = None
            for item in status.evidence_chain:
                ag = item.get("agent")
                res = item.get("result", {})
                if ag == "passion_mapper":
                    passions_obj = PassionProfile(**res)
                elif ag == "friction_detector":
                    frictions_obj = FrictionProfile(**res)
                elif ag == "cognitive_profiler":
                    cognitive_obj = CognitiveStyle(**res)
                elif ag == "resonance_synthesizer":
                    bridge_obj = AuthenticBridge(**res)

            status.holistic_profile = HolisticProfile(
                username=input_data.get("target_profile", {}).get("username", "target"),
                passions=passions_obj,
                frictions=frictions_obj,
                cognitive=cognitive_obj,
                bridge=bridge_obj,
                overall_confidence=self._holistic_confidence(status.agent_runs)
            )
            self._log("INFO", "[" + task_id + "] 360 İnsan Tanıma Profili Oluşturuldu")

            # --- P1 + P7 + P8 DERİNLİK VE GERÇEKLİK ANALİZİ (QuoteGuard Korumalı) ---
            # depth_analyst ana döngü dışında çalışır; success/failure must be
            # recorded on status.agent_runs so DecisionEngine sees the gap
            # instead of silently treating depth as unused.
            depth_start = datetime.now(timezone.utc)
            try:
                depth_agent = self.agents.get("depth_analyst") or DepthAnalyst(self.llm_gateway)
                with self._capture_llm_calls(task_id, "depth_analyst") as depth_scope:
                    depth_rep = await depth_agent.analyze(input_data, status.evidence_chain)
                depth_end = datetime.now(timezone.utc)
                status.depth_report = depth_rep.model_dump()
                status.depth_report["_provenance"] = self._provenance_for(
                    "depth_analyst", depth_rep, depth_scope.records
                )
                _depth_summary = dict(status.depth_report)
                status.agent_runs["depth_analyst"] = AgentRun(
                    task_id=task_id, agent_name="depth_analyst", status="completed",
                    started_at=depth_start, completed_at=depth_end,
                    output_summary=_depth_summary, call_ids=list(depth_scope.call_ids),
                    confidence=(
                        getattr(depth_rep, "reality_index", None)
                        if isinstance(getattr(depth_rep, "reality_index", None), (int, float))
                        else None
                    ),
                )
                q_stats = depth_rep.quote_guard or {}
                kept = q_stats.get("kept", len(depth_rep.reality_findings))
                checked = q_stats.get("checked", kept + q_stats.get("dropped_fake_quote", 0))
                self._log("INFO", f"[{task_id}] DERİNLİK TURU: gerçeklik endeksi %{int(depth_rep.reality_index * 100)}")
                self._log("INFO", f"[{task_id}] KALKAN: {kept}/{checked} bulgu kanıtla ayakta")
            except Exception as e:
                depth_end = datetime.now(timezone.utc)
                error_code = type(e).__name__
                status.agent_runs["depth_analyst"] = AgentRun(
                    task_id=task_id, agent_name="depth_analyst", status="failed",
                    started_at=depth_start, completed_at=depth_end,
                    error_code=error_code,
                    error_message=str(e)[:200],
                )
                status.evidence_chain.append({
                    "agent": "depth_analyst",
                    "evidence_type": "execution_failure",
                    "result": {"error_code": error_code, "error_message": str(e)[:250]},
                    "timestamp": depth_end.isoformat(),
                })
                status.depth_report = {
                    "available": False,
                    "reason": "DEPTH_ANALYSIS_UNAVAILABLE",
                    "error_code": error_code,
                    "error_message": str(e)[:250],
                }
                self._log("WARNING", f"[{task_id}] Derinlik analizi atlandı: {e}")



            # --- 5. ve 6. DAMGA: SHADOW & OSINT FORENSİKLERİ ---
            # Bu iki ajan ana döngünün dışında çalıştığı için, başarılı/başarısız
            # durumlarını da status.agent_runs'a kaydediyoruz ki DecisionEngine
            # onları görsün ve sessizce "COMPLETED" damgalanmasınlar.
            try:
                with self._capture_llm_calls(task_id, "shadow_executor") as shadow_scope:
                    shadow_result = await self.agents["shadow_executor"].execute(input_data)
                status.shadow_profile = shadow_result.model_dump()
                status.shadow_profile["_provenance"] = self._provenance_for(
                    "shadow_executor", shadow_result, shadow_scope.records
                )
                _shadow_summary = shadow_result.model_dump() if hasattr(shadow_result, "model_dump") else {}
                _shadow_summary["_provenance"] = status.shadow_profile["_provenance"]
                status.agent_runs["shadow_executor"] = AgentRun(
                    task_id=task_id, agent_name="shadow_executor", status="completed",
                    started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                    output_summary=_shadow_summary, call_ids=list(shadow_scope.call_ids),
                    confidence=(
                        getattr(shadow_result, "confidence", None)
                        if isinstance(getattr(shadow_result, "confidence", None), (int, float))
                        and getattr(shadow_result, "data_confidence", True)
                        else None
                    ),
                    warnings=[] if getattr(shadow_result, "data_confidence", True) else [
                        getattr(shadow_result, "fallback_reason", None) or "data_unavailable"
                    ],
                )
                self._log("INFO", f"[{task_id}] GÖLGE FORENSİĞİ: Manipülasyon ve NLP dizisi eklendi")
            except Exception as e:
                status.agent_runs["shadow_executor"] = AgentRun(
                    task_id=task_id, agent_name="shadow_executor", status="failed",
                    started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                    error_message=str(e)[:200],
                )
                self._log("WARNING", f"[{task_id}] Gölge forensiği atlandı: {e}")

            try:
                with self._capture_llm_calls(task_id, "osint_investigator") as osint_scope:
                    osint_result = await self.agents["osint_investigator"].execute(input_data)
                status.osint_footprint = osint_result.model_dump() if hasattr(osint_result, "model_dump") else osint_result
                status.osint_footprint["_provenance"] = self._provenance_for(
                    "osint_investigator", osint_result, osint_scope.records
                )
                data_conf = getattr(osint_result, "data_confidence", True)
                fallback = getattr(osint_result, "fallback_reason", None)
                status.agent_runs["osint_investigator"] = AgentRun(
                    task_id=task_id, agent_name="osint_investigator", status="completed",
                    started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                    output_summary=status.osint_footprint, call_ids=list(osint_scope.call_ids),
                    confidence=(
                        getattr(osint_result, "confidence", None)
                        if data_conf and isinstance(getattr(osint_result, "confidence", None), (int, float))
                        else None
                    ),
                    warnings=[] if data_conf else [fallback or "data_unavailable"],
                )
                self._log("INFO", f"[{task_id}] DİJİTAL AYAK İZİ: Platform varlık skorlaması yapıldı")
            except Exception as e:
                status.agent_runs["osint_investigator"] = AgentRun(
                    task_id=task_id, agent_name="osint_investigator", status="failed",
                    started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                    error_message=str(e)[:200],
                )
                self._log("WARNING", f"[{task_id}] OSINT taraması atlandı: {e}")

            # Determine final status via DecisionEngine
            final_status = self.decision_engine.make_decision(status.agent_runs)
            status.status = final_status
            
            if final_status == PipelineStatus.PARTIALLY_COMPLETED:
                failed_agents = [name for name, run in status.agent_runs.items() if run.status in ("failed", "halted")]
                self._log("WARNING", f"[{task_id}] TAMAMLANDI (KISMİ). Başarısız ajanlar: {', '.join(failed_agents)}")
            else:
                self._log("INFO", f"[{task_id}] TAMAMLANDI. Kanıt adımı: {len(status.evidence_chain)}")
                
            status.completed_at = datetime.now(timezone.utc)
            await self.memory.merge_evidence(task_id, status.evidence_chain)
            self._snapshot(status)
            
            # P0-FIX: Gercek SHA-256 kanit hash'i ve gercek sure (ms)
            import hashlib, json as _json
            _chain_bytes = _json.dumps(status.evidence_chain, default=str, sort_keys=True).encode()
            _real_hash = hashlib.sha256(_chain_bytes).hexdigest()
            _duration_ms = int((datetime.now(timezone.utc) - _task_wall_start).total_seconds() * 1000)
            self._emit(TaskCompletedEvent(
                task_id=task_id,
                agent_name="PinealExecutor",
                final_result_hash=_real_hash,
                duration_ms=_duration_ms
            ))
        except InsufficientEvidenceError as e:
            self._log("ERROR", "[" + task_id + "] KANIT KILIDI: " + str(e))
            status.status = "halted_evidence"
            status.completed_at = datetime.now(timezone.utc)
            await self.memory.merge_evidence(task_id, status.evidence_chain)
            self._snapshot(status)
        return status

    def _store_authentic_vector(self, input_data: Dict[str, Any], subject: str, vector: dict | None) -> None:
        """Store a vector only when it was actually calculated from the supplied data.

        A missing vector is represented explicitly in metadata.  It must never be
        replaced with neutral-looking numeric values because downstream resonance
        calculations treat numeric vectors as decision-ready evidence.

        Successful vectors carry an epistemic marker so consumers can distinguish
        LLM-derived estimates from measured evidence without mistaking the
        numbers for ground truth.
        """
        vector_key = f"{subject}_authentic_vector"
        status_key = f"{subject}_authentic_vector_status"
        if vector is None:
            input_data.pop(vector_key, None)
            input_data[status_key] = {
                "available": False,
                "reason": "AUTHENTIC_VECTOR_UNAVAILABLE",
                "epistemic": "unavailable",
            }
            return

        # Stamp the vector itself so any downstream consumer (resonance, UI,
        # evidence export) can see the estimate is model-derived, not measured.
        stamped = dict(vector)
        stamped.setdefault("_epistemic", "model_estimate")
        stamped.setdefault("_provenance", "authentic_vector_llm")
        input_data[vector_key] = stamped
        input_data[status_key] = {
            "available": True,
            "reason": None,
            "epistemic": "model_estimate",
            "provenance": "authentic_vector_llm",
        }

    @staticmethod
    def _holistic_confidence(agent_runs: Dict[str, AgentRun]) -> float:
        """Aggregate only measured confidence values; absence is not neutral confidence."""
        profile_agents = ("passion_mapper", "friction_detector", "cognitive_profiler", "resonance_synthesizer")
        values = [
            run.confidence for name, run in agent_runs.items()
            if name in profile_agents and run.status == "completed" and isinstance(run.confidence, (int, float))
        ]
        return round(sum(values) / len(values), 3) if values else 0.0

    async def _calculate_authentic_vector(self, data_dict: dict) -> dict | None:
        import json
        from pydantic import BaseModel
        
        class AuthenticVectorResult(BaseModel):
            depth: float
            energy: float
            achilles_heel: str
            core_wound: str
            dark_detail: str

        prompt = (
            "Sen Pineal-Heretic analitik motorunun baş teşhis uzmanısın (Frekans ve Yara Çıkarıcı).\n"
            "Aşağıdaki veri profilini incele ve şu hedefleri eksiksiz yerine getir:\n"
            "1. 'depth' (psikolojik karmaşıklık, zeka, saklanma) ve 'energy' (agresyon, yoğunluk, dışa vurum) değerlerini 0.1 ile 1.0 arasında derecelendir.\n"
            "2. 'achilles_heel' (Aşil Tendonu): Hedefin zırhındaki o en zayıf, tek bir darbeyle yıkılacağı hassas noktayı (örneğin: terk edilme korkusu, yetersizlik hissi) acımasızca tespit et.\n"
            "3. 'core_wound' (Ana Yara İz): Hedefin tüm savunma mekanizmalarını (maskesini) inşa etmesine sebep olan o geçmiş travmayı veya çocukluk yarasını tanımla.\n"
            "4. 'dark_detail' (Karanlık Detay): Metinlerdeki veya eylemlerindeki en çiğ, en saklamaya çalıştığı ama sızan o çelişkili veya karanlık arzuyu/detayı bul.\n"
            "DİKKAT: ASLA KİBAR OLMA. ASLA YUMUŞATMA. En acımasız, çiğ ve analitik tespiti yap.\n\n"
            f"Profil Verisi:\n{json.dumps(data_dict, ensure_ascii=False)[:3000]}\n\n"
            "Sadece belirtilen alanları içeren geçerli bir JSON döndür."
        )
        try:
            res = await self.llm_gateway.query_json(prompt, AuthenticVectorResult, tier=1)
            return {
                "depth": round(max(0.1, min(res.depth, 1.0)), 3), 
                "energy": round(max(0.1, min(res.energy, 1.0)), 3),
                "achilles_heel": res.achilles_heel,
                "core_wound": res.core_wound,
                "dark_detail": res.dark_detail
            }
        except Exception as e:
            # Do not manufacture a neutral-looking vector.  A numeric fallback
            # would be consumed by ResonanceCalculator as real user evidence.
            self._log("WARNING", f"Vektör hesaplanamadı; veri kullanılamaz olarak işaretlendi: {e}")
            return None

executor = PinealExecutor()

