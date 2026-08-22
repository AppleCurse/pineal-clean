from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any

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
        has_target = 'target_profile' in input_data
        has_user = 'user_profile' in input_data
        
        agents = []
        reasoning = []
        
        # Her zaman önce kendine ayna tut
        if has_user:
            agents.append('mirror_truth')
            reasoning.append("Kullanıcı frekansı tespiti zorunlu")
        
        # Hedef varsa 360 derece analiz et
        if has_target:
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
