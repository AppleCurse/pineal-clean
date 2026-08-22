import random
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class RewardSchedule(Enum):
    """
    B.F. Skinner'in operant conditioning schedule'ları
    """
    FIXED_RATIO = "fixed"      # Her 4 mesajda 1 ödül (Öngörülebilir, sıkıcı)
    VARIABLE_RATIO = "variable"  # Ortalama 4'te 1 ama unpredictable (BAĞIMLILIK)
    FIXED_INTERVAL = "fixed_time"  # Her 30 dakikada 1 (Tahmin edilebilir)
    VARIABLE_INTERVAL = "var_time"  # Ortalama 30 dk ama değişken (Yüksek bağımlılık)

@dataclass
class DopamineProfile:
    """
    Hedefin bağımlılık profili - neye nasıl tepki verir
    """
    # Temel ihtiyaçler (Maslow'un eksikleri)
    validation_need: float      # 0-1 (Onaylanma açlığı)
    novelty_seeking: float      # 0-1 (Yenilik arayışı)
    uncertainty_tolerance: float # 0-1 (Belirsizliğe dayanıklılık)
    
    # Bağımlılık göstergeleri
    chase_sensitivity: float    # "Peşinde koşma" eğilimi
    loss_chasing: bool          # Kaybettikçe devam etme
    near_miss_sensitivity: float  # "Neredeyse oldu" hissi
    
    # Optimal schedule
    optimal_reward: RewardSchedule
    optimal_interval: int       # Saniye cinsinden ortalama aralık

class DopamineEngine:
    """
    Hedefi "istemsiz" olarak etkileşime zorlayan motor.
    """
    
    def __init__(self):
        self.interaction_history = []
        self.reward_count = 0
        self.last_reward_time = 0
        
    def analyze_addiction_profile(self, target_data: Dict) -> DopamineProfile:
        """
        Hedefin bağımlılık eğilimlerini haritala.
        """
        text = ' '.join(target_data.get('posts', [])).lower()
        if not text and 'bio' in target_data:
            text = target_data['bio'].lower()
            
        # Validation need (Onay açlığı)
        validation_markers = ['beğeni', 'yorum', 'fikriniz', 'ne düşünüyorsunuz', 
                             'onay', 'kabul', 'sevilmek', 'görülmek']
        val_score = sum(text.count(m) for m in validation_markers) * 0.1
        
        # Novelty seeking (Yenilik arayışı)
        novelty_markers = ['sıkıldım', 'yeni', 'farklı', 'değişim', 'heyecan', 'macera']
        nov_score = sum(text.count(m) for m in novelty_markers) * 0.15
        
        # Chase sensitivity (Peşinde koşma)
        chase_markers = ['pes etmem', 'devam', 'bir daha', 'son bir', 'denemeliyim']
        chase_score = sum(text.count(m) for m in chase_markers) * 0.2
        
        # Loss chasing (Kayıp peşinde koşma)
        loss_chase = any(w in text for w in ['kaybettim', 'yenildim', 'olmadi', 'bu sefer'])
        
        # Optimal schedule belirle
        if chase_score > 0.6 and val_score > 0.5:
            schedule = RewardSchedule.VARIABLE_RATIO
            interval = random.randint(180, 900)  # 3-15 dk arası değişken
        elif nov_score > 0.6:
            schedule = RewardSchedule.VARIABLE_INTERVAL
            interval = random.randint(600, 3600)  # 10-60 dk
        else:
            schedule = RewardSchedule.FIXED_RATIO
            interval = 300  # 5 dk sabit
        
        return DopamineProfile(
            validation_need=min(val_score, 1.0),
            novelty_seeking=min(nov_score, 1.0),
            uncertainty_tolerance=random.uniform(0.3, 0.8),
            chase_sensitivity=min(chase_score, 1.0),
            loss_chasing=loss_chase,
            near_miss_sensitivity=0.7 if loss_chase else 0.4,
            optimal_reward=schedule,
            optimal_interval=interval
        )
    
    def generate_interaction_sequence(self, 
                                     profile: DopamineProfile,
                                     message_count: int = 10) -> List[Dict]:
        """
        Bağımlılık yaratan mesaj zinciri.
        Her mesaj bir "spin" - bazen ödül, bazen near-miss.
        """
        
        sequence = []
        
        for i in range(message_count):
            # Reward determination (Değişken ödül)
            reward = self._should_reward(profile, i)
            
            # Message type
            if reward:
                msg_type = "jackpot"  # Tam dopamin
            elif self._is_near_miss(profile):
                msg_type = "near_miss"  # Neredeyse oldu
            else:
                msg_type = "loss"  # Kayıp ama devam etme sinyali
            
            message = self._craft_gamble_message(msg_type, profile)
            
            sequence.append({
                'order': i + 1,
                'type': msg_type,
                'content': message,
                'delay_after': self._calculate_delay(profile),
                'dopamine_spike': self._estimate_dopamine(msg_type, profile)
            })
        
        return sequence
    
    def _should_reward(self, profile: DopamineProfile, turn: int) -> bool:
        """
        Değişken oranlı ödül sistemi.
        Öngörülemez ama ortalama belirli.
        """
        if profile.optimal_reward == RewardSchedule.VARIABLE_RATIO:
            # Ortalama her 4'te 1 ama tamamen rastgele
            # Örn: 0.25 olasılık ama clustering olabilir (2 ödül üst üste, sonra 6 boş)
            return random.random() < 0.25
        
        elif profile.optimal_reward == RewardSchedule.FIXED_RATIO:
            # Her 4. mesajda kesin ödül
            return turn % 4 == 0
        
        else:
            return random.random() < 0.3
    
    def _is_near_miss(self, profile: DopamineProfile) -> bool:
        """
        "Neredeyse kazanacaktım" hissi - en tehlikeli bağımlılık tetikleyicisi.
        """
        if not profile.near_miss_sensitivity:
            return False
        
        # %40 ihtimalle near-miss (Kayıptan daha çok dopamin)
        return random.random() < 0.4
    
    def _craft_gamble_message(self, msg_type: str, profile: DopamineProfile) -> str:
        """
        Kumar makinesi mesajları.
        """
        
        if msg_type == "jackpot":
            # Tam ödül - Yüksek dopamin
            jackpots = [
                "Tam olarak bunu hissetmiştim... Seninle aynı frekanstayım.",
                "Bu kadarını beklemiyordum. Derin bir yerden konuşuyorsun.",
                "Nadir biriyle karşılaştığımı biliyorum. Bu hissi unutamam."
            ]
            return random.choice(jackpots)
        
        elif msg_type == "near_miss":
            # Neredeyse oldu - Devam etme isteği
            near_misses = [
                "Bir adım daha yaklaşsaydın tam olarak... Ama şimdi anlıyorum.",
                "Neredeyse seni kaybediyordum. O son cümle kurtardı.",
                "Daha fazlasını söylemek istiyorum ama... Belki sonra.",
                "O an tam anlaşılacaktım ama kayboldu. Tekrar denemeliyim."
            ]
            return random.choice(near_misses)
        
        else:  # loss
            # Kayıp ama umut ver - "Bir daha dene"
            losses = [
                "Anlamadım... Belki farklı bir şekilde ifade etmelisin.",
                "Şu an değil. Ama bırakma, yaklaşıyoruz.",
                "Daha derine inmeliyiz. Bu yüzeyde kaldık.",
                "Kayıp bir şeyler var. Bulana kadar devam etmeliyim."
            ]
            return random.choice(losses)
    
    def _calculate_delay(self, profile: DopamineProfile) -> int:
        """
        Yanıt gecikmesi - Bekleme bağımlılığı yaratır.
        """
        base = profile.optimal_interval
        
        if profile.optimal_reward == RewardSchedule.VARIABLE_INTERVAL:
            # Değişken bekleme - tahmin edilemez
            return random.randint(int(base * 0.5), int(base * 2.0))
        else:
            return base
    
    def _estimate_dopamine(self, msg_type: str, profile: DopamineProfile) -> float:
        """
        Tahmini dopamin salınımı (arbitrary units).
        """
        base = {
            'jackpot': 1.0,
            'near_miss': 0.8,  # Kumar makinelerinde near-miss jackpot'tan az etkili değil
            'loss': 0.2
        }
        
        multiplier = profile.validation_need + profile.chase_sensitivity
        return base.get(msg_type, 0) * min(multiplier, 1.5)
