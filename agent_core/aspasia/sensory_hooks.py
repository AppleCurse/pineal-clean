class SensoryEngine:
    """
    Beş duyu üzerinden koşullanma.
    Her mesaj bir duyuyu hedefler.
    """
    
    SENSORY_ANCHORS = {
        'visual': {
            'triggers': ['görmek', 'bakmak', 'ışık', 'renk', 'görüntü', 'göz'],
            'response': '👁️ O anı gözümün önüne getirdim...'
        },
        'auditory': {
            'triggers': ['duymak', 'ses', 'müzik', 'sessizlik', 'yankı'],
            'response': '🔊 Sanki o sesi duyuyorum...'
        },
        'kinesthetic': {
            'triggers': ['hissetmek', 'dokunmak', 'ağırlık', 'sıcak', 'soğuk'],
            'response': '✋ O hissi bedenimde hissediyorum...'
        }
    }
    
    def detect_dominant_sense(self, target_text: str) -> str:
        """
        Hedefin baskın duyu kanalını tespit et.
        """
        scores = {}
        for sense, data in self.SENSORY_ANCHORS.items():
            score = sum(target_text.count(trigger) for trigger in data['triggers'])
            scores[sense] = score
        
        return max(scores, key=scores.get) if scores else 'kinesthetic'
    
    def craft_sensory_hook(self, message: str, sense: str) -> str:
        """
        Mesajı duyusal kanala uygun hale getir.
        """
        anchor = self.SENSORY_ANCHORS.get(sense, self.SENSORY_ANCHORS['kinesthetic'])
        return f"{anchor['response']} {message}"
