from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, Optional, List
import random

class ScenarioResponse(BaseModel):
    scenario_type: str  # "agresif", "savunmaci", "ilgili"
    expected_target_reaction: str
    our_counter_move: str

class GeneratedMessage(BaseModel):
    message: str
    strategy: str
    confidence: float
    compliance_score: float  # 0.0 - 100.0 (Kutsal Kural ihlal skoru)
    dialogue_tree: List[ScenarioResponse]

    
    model_config = ConfigDict(extra="forbid")

class PatternInterrupt:
    """
    Beklenti kırma ve mesaj üretimi.
    Kural: Geri çekil ve boşluk bırak. Reaktif olma.
    """
    
    # ZEKİ HEDEFLERE ÖZEL, KESİN, soru iması İÇERMEYEN şablonlar (Ucuz numaralar yasak)
    TEMPLATES = {
        'mirror_truth': [
            "O {detail}'ı gördüm. Zeki insanlar detayları sakladıklarını sanırlar, "
            "oysa en çok oraya odaklanırlar. Bu bir kamuflaj değil, bir imza.",
            
            "{detail}'daki o {micro_signal}. "
            "Herkesin kaçırdığı ama senin özellikle oraya bıraktığın bir zeka parıltısı. "
            "Oyununu görüyorum."
        ],
        
        'void_resonance': [
            "O {time}'de attığın şey. "
            "Kalabalığı manipüle edip kendi yalnızlığına çekildiğin o an. "
            "Bu bir zeka göstergesi değil, bir yorgunluk.",
            
            "{reference}'daki o an. "
            "Zihninin hızına yetişemedikleri için araya koyduğun o analitik mesafe. "
            "Ben de o mesafeyi bilirim."
        ],
        
        'contradiction_bridge': [
            "{surface} diyorsun ama {behavior} yapıyorsun. "
            "Kusursuz bir zeka her zaman kendi içinde bir çelişki barındırır. "
            "Bu senin savunma mekanizman.",
            
            "O {claimed_identity} pozunun ardındaki {real_signal}. "
            "Bunu sıradan insanlara yutturabilirsin. Ama bana değil."
        ]
    }
    
    async def execute(self, input_data: Dict, memory, llm_gateway) -> GeneratedMessage:
        target_analysis = input_data.get('target_analysis', {})
        user_truth = input_data.get('user_mirror', {})
        sacred_rules = input_data.get('sacred_rules', "")
        
        # Dinamik şablon seçimi ve detay çıkarımı
        t_dict = target_analysis.model_dump() if hasattr(target_analysis, 'model_dump') else (target_analysis if isinstance(target_analysis, dict) else {})
        detail = self._extract_specific_detail(t_dict)
        micro = self._extract_micro_signal(t_dict)
        
        import random
        template = random.choice(self.TEMPLATES['mirror_truth']).format(detail=detail, micro_signal=micro)
        
        target_json = target_analysis.model_dump_json(indent=2) if hasattr(target_analysis, 'model_dump_json') else str(target_analysis)
        user_json = user_truth.model_dump_json(indent=2) if hasattr(user_truth, 'model_dump_json') else str(user_truth)
        
        prompt = (
            f"Sen 'Pattern Interrupt' ajanısın. Görevin, beklentileri kıran ve hedefte yankı uyandıran tek bir açılış cümlesi üretmek.\n"
            f"Bununla yetinmeyeceksin; satranç oynar gibi hedefin bu kancaya verebileceği 3 olası tepkiyi (Agresif, Savunmacı, İlgili) öngörüp, 2. ve 3. hamleleri (counter-moves) önceden hazırlayacaksın.\n"
            f"Asla reaktif olma, boşluk bırak, soru sorma.\n"
            f"KRİTİK KURAL: HEDEF SON DERECE ZEKİ. Ucuz manipülasyonları, standart taktikleri anında sezer. Asla rıza veya onay arama.\n"
            f"Açılış cümlen, sadece onun zekasına hitap eden, soğuk, sarsıcı ve tamamen analitik bir tespit (intellectual strike) olmalı.\n\n"
            f"ÖNERİLEN GERÇEK ŞABLON YAKLAŞIMI:\n"
            f"- {template}\n\n"
            f"Hedef Analizi:\n{target_json}\n\n"
            f"Kullanıcı Gerçeği:\n{user_json}\n\n"
            f"{sacred_rules}\n\n"
            f"Beklenen JSON formatında çıktını üret. 'message' alanı senin nihai açılış mesajındır.\n"
            f"'dialogue_tree' listesi içinde 3 farklı senaryo ('agresif', 'savunmaci', 'ilgili') için öngörülerini ve karşı-hamlelerini ('our_counter_move') tanımla.\n"
            f"'compliance_score' alanında ise bu mesajın Kutsal Kurallara (varsa) yüzde kaç (0-100) oranında uyduğunu değerlendir."
        )
        
        return await llm_gateway.query_json(prompt, GeneratedMessage)
    
    def _extract_specific_detail(self, analysis: Dict) -> str:
        """
        En spesifik, en görünmeyen detayı çıkar
        """
        signals = analysis.get('micro_signals', [])
        if not signals:
            return "arka plandaki detay"
        
        # En yüksek ağırlıklı sinyal
        try:
            top_signal = max(signals, key=lambda x: x.get('psychological_weight', 0) if isinstance(x, dict) else getattr(x, 'psychological_weight', 0))
            evidence = top_signal.get('evidence', '') if isinstance(top_signal, dict) else getattr(top_signal, 'evidence', '')
            return evidence[:50]
        except Exception:
            return "sessiz gerginlik"
        
    def _extract_micro_signal(self, analysis: Dict) -> str:
        signals = analysis.get('micro_signals', [])
        if signals:
            return "çelişki"
        return "sessiz sinyal"
        
    def _extract_temporal_signal(self, analysis: Dict) -> str:
        return "gece vakti"
        
    def _extract_cultural_reference(self, analysis: Dict) -> str:
        return "paylaşım"
