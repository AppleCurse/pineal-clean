from pydantic import BaseModel, ConfigDict
from typing import List, Dict

class RoutePlan(BaseModel):
    agents: List[str]
    reasoning: str
    priority: int  # 1: Kritik, 2: Normal, 3: Opsiyonel
    
    model_config = ConfigDict(extra="forbid")

class CognitiveRouter:
    """
    Hangi ajanların çalışacağına karar veren beyin.
    """
    
    async def analyze(self, input_data: Dict) -> RoutePlan:
        target = input_data.get("target_profile") or {}
        user = input_data.get("user_profile") or {}
        if not isinstance(target, dict):
            target = {}
        if not isinstance(user, dict):
            user = {}

        # A present-but-empty object is not analysis-ready input. Route only
        # agents that can receive actual target/user evidence.
        has_target = bool(
            target.get("username") or target.get("name") or target.get("bio")
            or target.get("posts") or target.get("images")
        )
        has_user = bool(
            user.get("bio") or user.get("posts") or user.get("private_rituals")
            or user.get("late_night_playlist") or user.get("secret_envies")
        )
        
        agents = []
        reasoning = []
        
        # Her zaman önce kendine ayna tut
        if has_user:
            agents.append('mirror_truth')
            reasoning.append("Kullanıcı frekansı tespiti zorunlu")
            # [SEC FIX] interpreter artık ana rotada OTOMATİK planlanmaz.
            # Open Interpreter kod-icra yüzeyidir ve kendi LLM istemcisiyle
            # LIVE/spend kapılarını atlayabildiğinden yalnızca
            # ENABLE_INTERPRETER=true iken executor registry'sine girer ve
            # yalnızca /api/experimental/interpreter/execute ile (varsayılan
            # 403 kapısı) açıkça çağrılır.
        
        # Hedef varsa 360 derece analiz et
        if has_target:
            # OSINT is a forensic stamp executed once by PinealExecutor after
            # the routed analysis. Keeping it out of this route prevents a
            # second provider call and AgentRun overwrite.

            agents.append('autonomous_verifier')
            reasoning.append("Otonom Teyit (Arama & Kanıt)")

            agents.append('human_behavior')
            reasoning.append("Hedef Davranış Analizi")

            agents.append('passion_mapper')
            reasoning.append("Tutku ve Neşe Haritalama")
            
            agents.append('friction_detector')
            reasoning.append("Hassasiyet ve Sınır Tespiti")
            
            agents.append('cognitive_profiler')
            reasoning.append("Bilişsel Ton ve Üslup")

            if 'visual_evidence' in input_data:
                agents.append('authenticity_auditor')
                reasoning.append("Özgünlük ve Tutarlılık Denetimi")
            
            # Kullanıcı da hedef de varsa rezonans ve sahici köprü hesapla
            if has_user:
                agents.append('resonance_calc')
                reasoning.append("Sahici Değer ve Uyum Hesabı")
                
                agents.append('pattern_interrupt')
                reasoning.append("İletişim Deseni")

                agents.append('resonance_synthesizer')
                reasoning.append("Sahici İletişim Köprüsü")
        
        return RoutePlan(
            agents=agents,
            reasoning=" | ".join(reasoning),
            priority=1 if has_target and has_user else 2
        )
