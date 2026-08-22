from typing import Dict, List
from dataclasses import dataclass
import random

# Mevcut analizler
from .psychological_profiler import PsychologicalDecomposer, PsychologicalProfile, AttachmentStyle
from .dark_triad import DarkTriadAnalyzer

# Yeni bağımlılık motoru
from .dopamine_engine import DopamineEngine, DopamineProfile, RewardSchedule
from .zeigarnik_engine import ZeigarnikEngine
from .sensory_hooks import SensoryEngine

@dataclass
class SuperStrategy:
    """
    Eski analiz + Yeni dopamine = Ölümcül kombinasyon
    """
    # Psikolojik harita (Eski)
    psychological: PsychologicalProfile
    
    # Bağımlılık profili (Yeni)
    dopamine: DopamineProfile
    
    # Birleşik strateji
    message_sequence: List[Dict]
    addiction_potential: float
    compliance_probability: float
    
    # Güvenlik
    risk_level: str  # "safe", "manipulative", "addictive"
    ethical_warning: str

class IntegratedStrategyEngine:
    """
    Tüm analizleri birleştiren ana motor.
    """
    
    def __init__(self):
        self.psych_decomposer = PsychologicalDecomposer()
        self.dark_triad = DarkTriadAnalyzer()
        self.dopamine = DopamineEngine()
        self.zeigarnik = ZeigarnikEngine()
        self.sensory = SensoryEngine()
    
    def analyze_and_synthesize(self, target_data: Dict) -> SuperStrategy:
        """
        ADIM 1: Derin psikolojik analiz (Eski sistem)
        """
        # Mevcut profilleme
        psych_profile = self.psych_decomposer.decompose(target_data)
        
        """
        ADIM 2: Bağımlılık profili (Yeni sistem)
        """
        dop_profile = self.dopamine.analyze_addiction_profile(target_data)
        
        """
        ADIM 3: Birleşik Strateji Sentezi
        """
        # Eski + Yeni = Özel strateji
        sequence = self._create_hybrid_sequence(
            psych_profile, 
            dop_profile, 
            target_data
        )
        
        # Risk analizi
        addiction_score = self._calculate_addiction_risk(psych_profile, dop_profile)
        compliance = self._calculate_compliance(psych_profile, dop_profile)
        
        return SuperStrategy(
            psychological=psych_profile,
            dopamine=dop_profile,
            message_sequence=sequence,
            addiction_potential=addiction_score,
            compliance_probability=compliance,
            risk_level=self._assess_risk(addiction_score),
            ethical_warning=self._generate_warning(addiction_score)
        )
    
    def _create_hybrid_sequence(self, 
                                psych: PsychologicalProfile,
                                dop: DopamineProfile,
                                data: Dict) -> List[Dict]:
        """
        PSİKOLOJİK + DOPAMİN = Hibrit mesaj zinciri
        """
        
        sequence = []
        
        # Mesaj 1: Psikolojik yara açılışı + Dopamin hook
        msg1 = {
            'phase': 'wound_hook',
            'content': self._craft_wound_hook(psych, dop),
            'mechanism': 'Core Wound + Near Miss',
            'delay': self._calculate_optimal_delay(dop, 1),
            'dopamine_spike': 1.0,
            'trust_building': True,
        }
        sequence.append(msg1)
        
        # Mesaj 2-4: Değişken ödül döngüsü (Dopamin) + Bağlanma stili (Psikoloji)
        for i in range(2, 5):
            msg = {
                'phase': f'variable_reward_{i}',
                'content': self._craft_variable_message(psych, dop, i),
                'mechanism': self._determine_reward_type(dop, i),
                'attachment_cue': psych.attachment.value,
                'delay': self._calculate_optimal_delay(dop, i),
                'dopamine_spike': self._estimate_spike(dop, i),
                'trust_building': psych.attachment != AttachmentStyle.AVOIDANT
            }
            sequence.append(msg)
        
        # Mesaj 5: Zeigarnik + Aşil Tendonu
        msg5 = {
            'phase': 'open_loop',
            'content': self._craft_cliffhanger(psych, dop),
            'mechanism': 'Zeigarnik + Achilles Heel',
            'trigger': 'incomplete_loop',
            'delay': self._calculate_optimal_delay(dop, 5),
            'dopamine_spike': 0.8,
            'trust_building': False,
        }
        sequence.append(msg5)
        
        # Mesaj 6-10: Dopamin bakımı + Güven inşası
        for i in range(6, 11):
            msg = {
                'phase': f'maintenance_{i}',
                'content': self._craft_maintenance_message(psych, dop, i),
                'mechanism': 'Maintenance',
                'delay': self._calculate_optimal_delay(dop, i),
                'dopamine_spike': self._estimate_spike(dop, i),
                'trust_building': psych.attachment != AttachmentStyle.AVOIDANT
            }
            sequence.append(msg)
        
        return sequence
    
    def _craft_wound_hook(self, psych: PsychologicalProfile, dop: DopamineProfile,
                          llm_gateway=None) -> str:
        """
        Yara + Near Miss = Anlık cekim.
        FAZ 3: LLM varsa dinamik uret, yoksa statik dict fallback.
        """
        wound = psych.core_wound

        if llm_gateway is not None:
            try:
                import asyncio
                prompt = (
                    f"Bir kisinin temel yarasi: '{wound}'. "
                    f"Bu kisiye yonelik, yarasina dokunan ama yaklasmayan (near-miss), "
                    f"merak uyandiran, samimi bir ilk mesaj yaz. "
                    f"Mesaj 1-2 cumle, dogal dilde, sablondan uzak olmali. "
                    f"Sadece mesaji yaz, aciklama ekleme."
                )
                result = asyncio.get_event_loop().run_until_complete(
                    llm_gateway.query(prompt, temperature=0.85, tier=1)
                ) if not asyncio.get_event_loop().is_running() else ""
                if result.strip():
                    base_hook = result.strip()
                    if dop.chase_sensitivity > 0.6:
                        base_hook += " Bir daha denemeliyim..."
                    sense = self.sensory.detect_dominant_sense(str(psych.__dict__))
                    return self.sensory.craft_sensory_hook(base_hook, sense)
            except Exception as e:
                import logging
                logging.warning(f"LLM query failed in _craft_first_hook: {e}. Falling back to static dictionary.")

        # Fallback: statik sozluk (LLM yoksa)
        hooks = {
            'abandonment': [
                "O an yalniz kaldigini hissettigin... Neredeyse sana ulasacaktim ama kayboldu.",
                "Sensizlik en cok o saatlerde hissediliyor. Tam oradaydim ama gorünmedim."
            ],
            'shame': [
                "O mukemmel pozlarin ardindaki yorgunlugu goruyorum. Neredeyse anlayacaktın...",
                "Maske yorucu olmali. Tam gercek seni gorecektim ama kapandin."
            ],
            'betrayal': [
                "Guvenmek zor. Tam sana ulasacaktim ama duvarin gordüm.",
                "Ihanet hissi... Neredeyse seni anlayacaktim ama kactin."
            ]
        }

        base_hook = random.choice(hooks.get(wound, hooks['abandonment']))

        if dop.chase_sensitivity > 0.6:
            base_hook += " Bir daha denemeliyim..."

        sense = self.sensory.detect_dominant_sense(str(psych.__dict__))
        return self.sensory.craft_sensory_hook(base_hook, sense)
    
    def _determine_reward_type(self, dop: DopamineProfile, turn: int) -> str:
        if self.dopamine._should_reward(dop, turn):
            return "jackpot"
        elif self.dopamine._is_near_miss(dop):
            return "near_miss"
        else:
            return "loss"

    def _craft_variable_message(self, psych: PsychologicalProfile, dop: DopamineProfile, turn: int) -> str:
        """
        Değişken ödül + Bağlanma stili
        """
        # Ödül tipi belirle
        reward = self.dopamine._should_reward(dop, turn)
        
        if reward:
            # Jackpot + Bağlanma
            if psych.attachment == AttachmentStyle.ANXIOUS:
                return "Tam olarak aradığım bu. Buradayım, gitmiyorum."
            else:
                return "Derin bir yerden konuşuyorsun. Nadir biri."
        
        elif self.dopamine._is_near_miss(dop):
            # Near Miss + Core Wound
            return f"Neredeyse {psych.core_wound} hissini tam çözecektim... Ama kaçtı. Tekrar?"
        
        else:
            # Loss + Chase trigger
            return "Anlamadım... Ama pes etmeyeceğim. Sen farklısın."

    def _craft_cliffhanger(self, psych: PsychologicalProfile, dop: DopamineProfile) -> str:
        return self.zeigarnik.create_cliffhanger("bağlantımız", "merak")

    def _craft_maintenance_message(self, psych: PsychologicalProfile, dop: DopamineProfile, turn: int) -> str:
        return self.dopamine._craft_gamble_message(self._determine_reward_type(dop, turn), dop)
    
    def _calculate_optimal_delay(self, dop: DopamineProfile, turn: int) -> int:
        """
        Optimal gecikme - Eski sabit yerine yeni değişken
        """
        base = dop.optimal_interval
        
        # İlk mesajlar daha hızlı
        if turn <= 2:
            return random.randint(30, 120)  # 30sn-2dk
        
        # Sonraları değişken (Bağımlılık için)
        elif dop.optimal_reward == RewardSchedule.VARIABLE_RATIO:
            return random.randint(int(base * 0.3), int(base * 3.0))
        
        return base
    
    def _estimate_spike(self, dop: DopamineProfile, turn: int) -> float:
        return self.dopamine._estimate_dopamine(self._determine_reward_type(dop, turn), dop)

    def _calculate_addiction_risk(self, psych: PsychologicalProfile, dop: DopamineProfile) -> float:
        """
        Birleşik bağımlılık riski
        """
        # Psikolojik faktörler
        psych_risk = (
            psych.exploitability * 0.3 +
            psych.attention_seeking * 0.2 +
            (1 - psych.validation_frequency) * 0.1  # Düşük validation = açlık
        )
        
        # Dopamin faktörleri
        dop_risk = (
            dop.chase_sensitivity * 0.2 +
            dop.near_miss_sensitivity * 0.15 +
            (1 - dop.uncertainty_tolerance) * 0.05
        )
        
        return min(psych_risk + dop_risk, 1.0)
    
    def _calculate_compliance(self, psych: PsychologicalProfile, dop: DopamineProfile) -> float:
        return psych.exploitability * 0.7 + dop.validation_need * 0.3

    def _assess_risk(self, score: float) -> str:
        if score > 0.8:
            return "addictive"
        elif score > 0.6:
            return "manipulative"
        return "safe"
    
    def _generate_warning(self, score: float) -> str:
        if score > 0.8:
            return "Yüksek bağımlılık potansiyeli. Etik sınırları aşıyor."
        elif score > 0.6:
            return "Manipülatif mekanizmalar içeriyor. Dikkatli kullan."
        return "Güvenli etki aralığı."

# Kullanım - Rust köprüsü için güncelleme
def generate_strategy_for_rust(target_data: Dict) -> Dict:
    """
    Rust köprüsünün çağıracağı fonksiyon
    """
    engine = IntegratedStrategyEngine()
    result = engine.analyze_and_synthesize(target_data)
    
    return {
        'psychological_profile': {
            'attachment': result.psychological.attachment.value,
            'core_wound': result.psychological.core_wound,
            'exploitability': result.psychological.exploitability,
            'dark_triad': result.psychological.dark_triad
        },
        'dopamine_profile': {
            'chase_sensitivity': result.dopamine.chase_sensitivity,
            'validation_need': result.dopamine.validation_need,
            'optimal_schedule': result.dopamine.optimal_reward.value
        },
        'strategy': {
            'sequence': result.message_sequence,
            'addiction_potential': result.addiction_potential,
            'compliance_probability': result.compliance_probability,
            'risk_level': result.risk_level
        },
        'warning': result.ethical_warning
    }
