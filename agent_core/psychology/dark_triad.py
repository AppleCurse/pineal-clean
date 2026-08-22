from pydantic import BaseModel, ConfigDict
from typing import Dict, List
import re

class DarkTriadProfile(BaseModel):
    machiavellianism: float = 0.0
    narcissism: float = 0.0
    psychopathy: float = 0.0
    exploitability: float = 0.0
    
    model_config = ConfigDict(extra="forbid")

class DarkTriadAnalyzer:
    MARKERS = {
        'machiavellianism': ['strateji', 'taktik', 'oyun', 'kontrol', 'piyon'],
        'narcissism': ['mükemmel', 'eşsiz', 'olağanüstü', 'benzersiz', 'seçilmiş'],
        'psychopathy': ['risk', 'tehlike', 'sınır', 'çılgın', 'kural']
    }
    
    def analyze(self, profile_data: Dict) -> DarkTriadProfile:
        text = ' '.join(profile_data.get('posts', []) + [profile_data.get('bio', '')]).lower()
        
        scores = {
            trait: sum(text.count(word) for word in words) * 0.1 
            for trait, words in self.MARKERS.items()
        }
        
        # Exploitability hesapla
        exploit = 0.5
        if scores['narcissism'] > 0.7 and scores['machiavellianism'] < 0.4:
            exploit = 0.9
        elif scores['machiavellianism'] > 0.6:
            exploit = 0.3
            
        return DarkTriadProfile(
            machiavellianism=min(scores['machiavellianism'], 1.0),
            narcissism=min(scores['narcissism'], 1.0),
            psychopathy=min(scores['psychopathy'], 1.0),
            exploitability=exploit
        )
    
    def generate_strategy(self, profile: DarkTriadProfile) -> Dict:
        if profile.narcissism > 0.7:
            return {'vector': 'mirroring', 'tactic': 'Özel ve seçilmiş hissettir'}
        elif profile.machiavellianism > 0.6:
            return {'vector': 'alliance', 'tactic': 'Karşılıklı çıkar vurgusu'}
        elif profile.psychopathy > 0.5:
            return {'vector': 'thrill', 'tactic': 'Risk ve heyecan'}
        return {'vector': 'empathy', 'tactic': 'Duygusal rezonans'}
