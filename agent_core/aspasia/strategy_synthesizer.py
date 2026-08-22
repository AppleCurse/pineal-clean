from dataclasses import dataclass
from typing import Dict
import random

@dataclass
class MessageStrategy:
    hook: str
    line_2: str
    line_3: str
    compliance_probability: float

class StrategySynthesizer:
    """Asla reddedilmeyecek strateji üretir."""
    
    def synthesize(self, profile, achilles, user_profile) -> MessageStrategy:
        wound = profile.core_wound
        attachment = profile.attachment.value
        
        # Hook seçimi
        hooks = {
            'abandonment': [
                "O gece yarısı paylaşım... Yalnızlık hissettiğin ama söyleyemediğin",
                "Sensizlik en çok o saatlerde hissediliyor, değil mi?"
            ],
            'shame': [
                "Maske yorucu olmalı. Gerçek seni görmek istiyorum",
                "O mükemmel pozların ardındaki yorgunluğu görüyorum"
            ],
            'betrayal': [
                "Güvenmek zor. Özellikle geçmişten sonra",
                "Samimiyetini test eden biri olmalısın sürekli"
            ]
        }
        
        hook = random.choice(hooks.get(wound, hooks['abandonment']))
        
        # Yara rezonansı
        resonances = {
            'abandonment': "O an yalnız kaldığını hissettiğin, ama kimseye söyleyemediğin...",
            'shame': "Görünenden daha derin olduğunu biliyorum.",
            'betrayal': "Güvenmek zor. Özellikle geçmişte yaşananlardan sonra."
        }
        line2 = resonances.get(wound, resonances['abandonment'])
        
        # Güven inşası
        if attachment == 'anxious':
            line3 = "Buradayım. Gitmeyeceğim."
        elif attachment == 'avoidant':
            line3 = "Sana alan veriyorum. Baskı yok."
        else:
            line3 = "Seninle aynı frekanstayım."
        
        # Compliance hesaplama
        prob = profile.exploitability * 100
        
        return MessageStrategy(
            hook=hook,
            line_2=line2,
            line_3=line3,
            compliance_probability=prob
        )
