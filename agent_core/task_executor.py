import asyncio, os, tempfile
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone

try:
    from agent_core.services.cognitive_router import CognitiveRouter, RoutePlan
    from agent_core.services.canonical_memory import CanonicalMemory
    from agent_core.services.uncertainty_engine import UncertaintyEngine
    from agent_core.services.llm_gateway import LLMGateway
    from agent_core.agents.passion_mapper import PassionMapperAgent
    from agent_core.agents.friction_detector import FrictionDetectorAgent
    from agent_core.agents.cognitive_profiler import CognitiveProfilerAgent
    from agent_core.agents.resonance_synthesizer import ResonanceSynthesizerAgent
    from agent_core.agents.human_behavior import HumanBehaviorAnalyzer
    from agent_core.agents.mirror_truth import MirrorOfTruth
    from agent_core.agents.resonance_calculator import ResonanceCalculator
    from agent_core.agents.pattern_interrupt import PatternInterrupt
    from agent_core.services.memory_injector import MemoryInjector
    from agent_core.services.search_engine import SearchEngine
    from agent_core.agents.autonomous_verifier import AutonomousVerifier
    from agent_core.agents.interpreter_agent import InterpreterAgent
except Exception:
    from services.cognitive_router import CognitiveRouter, RoutePlan
    from services.canonical_memory import CanonicalMemory
    from services.uncertainty_engine import UncertaintyEngine
    from services.llm_gateway import LLMGateway
    from agents.passion_mapper import PassionMapperAgent
    from agents.friction_detector import FrictionDetectorAgent
    from agents.cognitive_profiler import CognitiveProfilerAgent
    from agents.resonance_synthesizer import ResonanceSynthesizerAgent
    from agents.human_behavior import HumanBehaviorAnalyzer
    from agents.mirror_truth import MirrorOfTruth
    from agents.resonance_calculator import ResonanceCalculator
    from agents.pattern_interrupt import PatternInterrupt
    from services.memory_injector import MemoryInjector
    from services.search_engine import SearchEngine
    from agents.autonomous_verifier import AutonomousVerifier
    from agents.interpreter_agent import InterpreterAgent

try:
    from agent_core.domain.memory_models import (
        TaskSnapshot, AgentRun, HolisticProfile, PassionProfile, FrictionProfile, CognitiveStyle, AuthenticBridge
    )
except Exception:
    from domain.memory_models import (
        TaskSnapshot, AgentRun, HolisticProfile, PassionProfile, FrictionProfile, CognitiveStyle, AuthenticBridge
    )

class InsufficientEvidenceError(RuntimeError):
    pass

class VerifiedNote(BaseModel):
    note: str

class TaskStatus(TaskSnapshot):
    pass

try:
    from agent_core.services.vision_analyzer import VisionAnalyzer, VisualEvidence
except Exception:
    from services.vision_analyzer import VisionAnalyzer, VisualEvidence

class PinealExecutor:
    def __init__(self, log_callback=None, emit_event_callback=None, snapshot_callback=None):
        self._log = log_callback or (lambda level, msg: None)
        self._emit = emit_event_callback or (lambda evt: None)
        self._snapshot_cb = snapshot_callback
        self.router = CognitiveRouter()
        self.memory = CanonicalMemory()
        self.injector = MemoryInjector()
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
            "mirror_truth": MirrorOfTruth(),
            "resonance_calc": ResonanceCalculator(),
            "pattern_interrupt": PatternInterrupt(),
            "autonomous_verifier": AutonomousVerifier(self.search_engine),
            "interpreter": InterpreterAgent(self.llm_gateway),
        }

    def _snapshot(self, status: TaskStatus):
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
        paths = []
        for u in urls[:2]:
            try:
                import httpx
                async with httpx.AsyncClient() as c:
                    r = await c.get(u, timeout=15)
                    r.raise_for_status()
                    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    tmp.write(r.content)
                    tmp.close()
                    paths.append(tmp.name)
            except Exception as e:
                self._log("WARNING", "Gorsel indirilemedi: " + str(e)[:60])
        return paths

    async def _deep_research(self, input_data, suspicious, agent_name):
        prompt = (
            "Onceki analiz supheli bulundu. Kanit: " + suspicious.model_dump_json() +
            "\nKurallar: 1) Emin degilsen 'bilmiyorum' de 2) Tahmin uretme 3) Sadece veride olanlari analiz et. Yeniden analiz et."
        )
        verified = await self.llm_gateway.query(prompt, temperature=0.1, tier=1)
        return VerifiedNote(note=verified)

    async def execute_task(self, input_data: Dict[str, Any], task_id: str) -> TaskStatus:
        from agent_core.schemas.telemetry import (
            TaskStartedEvent, StepCompletedEvent, ErrorHaltEvent, TaskCompletedEvent, GenericLogEvent, Severity
        )
        status = TaskStatus(task_id=task_id, status="processing", created_at=datetime.now(timezone.utc))
        input_data["sacred_rules"] = self.injector.fetch_active_rules()

        raw_imgs = input_data.get("target_profile", {}).get("images", [])
        if raw_imgs and isinstance(raw_imgs, list) and len(raw_imgs) > 0 and isinstance(raw_imgs[0], str) and raw_imgs[0].startswith("http"):
            self._log("INFO", f"[{task_id}] MULTIMODAL VISION: {len(raw_imgs)} fotoğraf görsel zeka ile inceleniyor...")
            try:
                target_bio = input_data.get("target_profile", {}).get("bio", "")
                visual_ev = await self.vision_analyzer.analyze_images(raw_imgs, target_context=target_bio)
                input_data["visual_evidence"] = visual_ev.model_dump()
                self._log("INFO", f"[{task_id}] GÖRSEL KANIT: {visual_ev.visual_evidence_summary}")
            except Exception as e:
                self._log("WARNING", f"[{task_id}] Vision analizi atlandı: {str(e)[:80]}")

        imgs = input_data.get("target_profile", {}).get("images", [])
        if imgs and isinstance(imgs[0], str) and imgs[0].startswith("http"):
            input_data["target_profile"]["images"] = await self._download_images(imgs)

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
                try:
                    agent = self.agents[agent_name]
                    try:
                        result = await agent.execute(input_data, self.memory, self.llm_gateway)
                    except TypeError:
                        result = await agent.execute(input_data)
                    if not isinstance(result, BaseModel):
                        raise TypeError(agent_name + " gecersiz cikti: " + str(type(result)))
                except InsufficientEvidenceError:
                    raise
                except Exception as e:
                    run.status = "failed"
                    run.error_code = type(e).__name__
                    run.error_message = str(e)[:200]
                    status.status = "failed"
                    status.completed_at = datetime.now(timezone.utc)
                    self._snapshot(status)
                    self._log("ERROR", f"[{task_id}] AGENT {agent_name} BASTARISIZ: {type(e).__name__}: {str(e)[:200]}")
                    self._emit(ErrorHaltEvent(
                        task_id=task_id,
                        agent_name=agent_name,
                        error_code=type(e).__name__,
                        error_message=str(e)[:200],
                        severity=Severity.Critical
                    ))
                    self._log("ERROR", f"[{task_id}] PIPELINE FAILED; silent continuation disabled")
                    await self.memory.merge_evidence(task_id, status.evidence_chain)
                    return status

                check = self.uncertainty.evaluate(result, agent_name)
                if check.confidence < 0.6:
                    halt_reason = f"Düşük güven ({check.confidence}). Router zinciri kesti."
                    self._log("ERROR", f"[{task_id}] COGNITIVE ROUTER: {halt_reason}")
                    run.status = "halted"
                    run.error_code = "LOW_CONFIDENCE"
                    run.error_message = halt_reason
                    status.halted_reason = halt_reason
                    self._snapshot(status)
                    raise InsufficientEvidenceError(halt_reason)

                if check.is_suspicious:
                    self._log("ERROR", "[" + task_id + "] UNCERTAINTY: " + check.reason)
                    try:
                        result = await self._deep_research(input_data, result, agent_name)
                    except Exception as e:
                        raise InsufficientEvidenceError("Supheli kanit dogrulanamadi: " + str(e)[:80])

                if agent_name == "mirror_truth":
                    input_data["user_mirror"] = result.model_dump()
                    input_data["user_authentic_vector"] = await self._calculate_authentic_vector(input_data["user_mirror"])
                elif agent_name == "human_behavior":
                    input_data["target_analysis"] = result.model_dump()
                    input_data["target_authentic_vector"] = await self._calculate_authentic_vector(input_data["target_analysis"])
                elif agent_name == "passion_mapper":
                    input_data["passions"] = result.model_dump()
                elif agent_name == "friction_detector":
                    input_data["frictions"] = result.model_dump()
                elif agent_name == "cognitive_profiler":
                    input_data["cognitive"] = result.model_dump()

                status.evidence_chain.append({"agent": agent_name, "result": result.model_dump(), "timestamp": datetime.now(timezone.utc).isoformat()})
                
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.output_summary = result.model_dump()
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
                    output_hash="HASH"
                ))

                if agent_name == "resonance_calc" and hasattr(result, "compatibility_score") and result.compatibility_score < 0.70:
                    self._log("ERROR", "[" + task_id + "] FREKANS UYUSMAZLIGI: " + str(round(result.compatibility_score, 2)))
                    status.status = "halted_frequency"
                    await self.memory.merge_evidence(task_id, status.evidence_chain)
                    self._snapshot(status)
                    return status

            for agent_name in deferred:
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
                try:
                    agent = self.agents[agent_name]
                    try:
                        result = await agent.execute(input_data, self.memory, self.llm_gateway)
                    except TypeError:
                        result = await agent.execute(input_data)
                except Exception as e:
                    run.status = "failed"
                    run.error_code = type(e).__name__
                    run.error_message = str(e)[:200]
                    status.status = "failed"
                    status.completed_at = datetime.now(timezone.utc)
                    self._snapshot(status)
                    self._log("ERROR", f"[{task_id}] AGENT {agent_name} BASTARISIZ: {type(e).__name__}: {str(e)[:200]}")
                    await self.memory.merge_evidence(task_id, status.evidence_chain)
                    return status
                    
                status.evidence_chain.append({"agent": agent_name, "result": result.model_dump(), "timestamp": datetime.now(timezone.utc).isoformat()})
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.output_summary = result.model_dump()
                run.confidence = 0.90
                if agent_name not in status.completed_agents:
                    status.completed_agents.append(agent_name)
                self._snapshot(status)

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
                overall_confidence=0.85 if bridge_obj else 0.5
            )
            self._log("INFO", "[" + task_id + "] 360 İnsan Tanıma Profili Oluşturuldu")

            status.status = "completed"
            status.completed_at = datetime.now(timezone.utc)
            await self.memory.merge_evidence(task_id, status.evidence_chain)
            self._snapshot(status)
            self._log("INFO", "[" + task_id + "] TAMAMLANDI. Kanit adimi: " + str(len(status.evidence_chain)))
            self._emit(TaskCompletedEvent(
                task_id=task_id,
                agent_name="PinealExecutor",
                final_result_hash="DONE",
                duration_ms=0
            ))
        except InsufficientEvidenceError as e:
            self._log("ERROR", "[" + task_id + "] KANIT KILIDI: " + str(e))
            status.status = "halted_evidence"
            status.completed_at = datetime.now(timezone.utc)
            await self.memory.merge_evidence(task_id, status.evidence_chain)
            self._snapshot(status)
        return status

    async def _calculate_authentic_vector(self, data_dict: dict) -> dict:
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
            self._log("WARNING", f"Vektör LLM üzerinden hesaplanamadı, fallback kullanılıyor: {e}")
            return {
                "depth": 0.5, 
                "energy": 0.5, 
                "achilles_heel": "Bilinmiyor", 
                "core_wound": "Bilinmiyor", 
                "dark_detail": "Bilinmiyor"
            }

executor = PinealExecutor()

