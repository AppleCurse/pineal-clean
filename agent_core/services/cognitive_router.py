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
        
        # Hedef varsa analiz et
        if has_target:
            agents.append('autonomous_verifier')
            reasoning.append("Otonom Teyit (Ayna)")
            
            agents.append('human_behavior')
            reasoning.append("Hedef mikro-analizi")
            
            # Kullanıcı da hedef de varsa rezonans hesapla
            if has_user:
                agents.append('resonance_calc')
                reasoning.append("Frekans uyumu kontrolü")
                
                # Uyum yüksekse desen kır
                agents.append('pattern_interrupt')
                reasoning.append("Yüksek uyum - Mesaj üretimi")
        
        return RoutePlan(
            agents=agents,
            reasoning=" | ".join(reasoning),
            priority=1 if has_target and has_user else 2
        )
