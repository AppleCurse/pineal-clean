import json
import re
from typing import Dict, List
from dataclasses import dataclass, asdict
from enum import Enum

class AttachmentStyle(Enum):
    SECURE = "secure"
    ANXIOUS = "anxious"
    AVOIDANT = "avoidant"
    DISORGANIZED = "disorganized"

@dataclass
class PsychologicalProfile:
    dark_triad: Dict[str, float]
    attachment: AttachmentStyle
    core_wound: str
    emotional_need: str
    fear: str
    exploitability: float
    attention_seeking: float
    validation_frequency: float

class PsychologicalDecomposer:
    """Hedefin psikolojik haritasını çıkarır."""
    
    def decompose(self, profile_data: Dict) -> PsychologicalProfile:
        text = self._extract_text(profile_data)
        
        # Analizler
        attachment = self._detect_attachment(text)
        wound = self._detect_wound(text)
        dark = self._calculate_dark_triad(text)
        
        return PsychologicalProfile(
            dark_triad=dark,
            attachment=attachment,
            core_wound=wound['type'],
            emotional_need=self._derive_need(wound, attachment),
            fear=wound['fear'],
            exploitability=self._calculate_exploitability(dark, attachment, wound),
            attention_seeking=self._score_attention(text),
            validation_frequency=self._score_validation(text)
        )
    
    def _extract_text(self, data: Dict) -> str:
        bio = data.get('bio', '')
        posts = ' '.join(data.get('posts', []))
        return f"{bio} {posts}".lower()
    
    def _detect_attachment(self, text: str) -> AttachmentStyle:
        anxious = len([w for w in ['yalnız', 'terk', 'sensiz', 'bekle'] if w in text])
        avoidant = len([w for w in ['özgürlük', 'bağımsız', 'mesafe'] if w in text])
        
        if anxious > avoidant:
            return AttachmentStyle.ANXIOUS
        elif avoidant > anxious:
            return AttachmentStyle.AVOIDANT
        return AttachmentStyle.SECURE
    
    def _detect_wound(self, text: str) -> Dict:
        wounds = {
            'abandonment': {'markers': ['terk', 'yalnız', 'sensiz'], 'fear': 'Terk edilme'},
            'shame': {'markers': ['utandım', 'ayıp', 'yetersiz'], 'fear': 'Aşağılanma'},
            'betrayal': {'markers': ['aldattı', 'güvenmem', 'yalan'], 'fear': 'İhanet'}
        }
        
        scores = {k: sum(text.count(m) for m in v['markers']) 
                 for k, v in wounds.items()}
        
        primary = max(scores, key=scores.get) if any(scores.values()) else 'abandonment'
        return {
            'type': primary,
            'fear': wounds[primary]['fear']
        }
    
    def _calculate_dark_triad(self, text: str) -> Dict[str, float]:
        mach = sum(text.count(w) for w in ['strateji', 'kontrol', 'oyun']) * 0.1
        narc = sum(text.count(w) for w in ['mükemmel', 'eşsiz', 'ben']) * 0.1
        psych = sum(text.count(w) for w in ['risk', 'tehlike', 'kuralsız']) * 0.1
        
        return {
            'machiavellianism': min(mach, 1.0),
            'narcissism': min(narc, 1.0),
            'psychopathy': min(psych, 1.0)
        }
    
    def _calculate_exploitability(self, dark, attachment, wound) -> float:
        score = 0.5
        
        if dark['narcissism'] > 0.7:
            score += 0.2
        if attachment == AttachmentStyle.ANXIOUS:
            score += 0.2
        if wound['type'] == 'abandonment':
            score += 0.1
            
        return min(score, 0.95)
    
    def _derive_need(self, wound, attachment):
        needs = {
            'abandonment': 'Güvenlik ve süreklilik',
            'shame': 'Kabul ve onay',
            'betrayal': 'Dürüstlük ve şeffaflık'
        }
        return needs.get(wound['type'], 'Anlaşılma')
    
    def _score_attention(self, text: str) -> float:
        selfie_refs = text.count('ben') + text.count('kendim')
        return min(selfie_refs * 0.05, 1.0)
    
    def _score_validation(self, text: str) -> float:
        question_marks = text.count('?')
        return min(question_marks * 0.1, 1.0)
