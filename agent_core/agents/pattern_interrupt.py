from pydantic import BaseModel, ConfigDict
from typing import Dict, List

class ScenarioResponse(BaseModel):
    scenario_type: str  # "agresif", "savunmaci", "ilgili"
    expected_target_reaction: str
    our_counter_move: str  # saygılı devam ifadesi (karşı-hamle manipülasyonu DEĞİL)

class GeneratedMessage(BaseModel):
    message: str
    strategy: str
    confidence: float
    compliance_score: float  # 0.0 - 100.0 (Kutsal Kural ihlal skoru)
    dialogue_tree: List[ScenarioResponse]
    data_confidence: bool = True
    fallback_reason: str | None = None

    
    model_config = ConfigDict(extra="forbid")

class PatternInterrupt:
    """
    Beklenti kırma ve mesaj üretimi.
    Kural: Geri çekil ve boşluk bırak. Reaktif olma.
    """

    # Tek gerçek gözlemden türetilen, kanıt DIŞI hiçbir ayrıntı eklemeyen
    # nötr cümle kılavuzları. Rastgele seçilmez, psikolojik iddia içermez,
    # manipülatif dil barındırmaz (eski random şablonlar kaldırıldı).
    OBSERVATION_FRAMES = (
        "Bu gözlemi doğrudan ifade eden, kanıt dışı ayrıntı eklemeyen tek cümle.",
        "Gözlemi samimi ve sade biçimde dile getiren, yorum katmayan tek cümle.",
        "Kanıtı olduğu gibi aktaran, tahmin ve teşhis içermeyen tek cümle.",
    )

    async def execute(self, input_data: Dict, memory, llm_gateway) -> GeneratedMessage:
        target_analysis = input_data.get('target_analysis', {})
        user_truth = input_data.get('user_mirror', {})
        sacred_rules = input_data.get('sacred_rules', "")
        
        # A message may only use source-tagged observations, never placeholder
        # details or inferred wounds.
        t_dict = target_analysis.model_dump() if hasattr(target_analysis, 'model_dump') else (target_analysis if isinstance(target_analysis, dict) else {})
        evidence = self._grounded_evidence(t_dict)
        if not evidence:
            return GeneratedMessage(
                message="",
                strategy="UNAVAILABLE",
                confidence=0.0,
                compliance_score=100.0,
                dialogue_tree=[],
                data_confidence=False,
                fallback_reason="insufficient_grounded_evidence",
            )
        detail = evidence[0]
        
        target_json = target_analysis.model_dump_json(indent=2) if hasattr(target_analysis, 'model_dump_json') else str(target_analysis)
        user_json = user_truth.model_dump_json(indent=2) if hasattr(user_truth, 'model_dump_json') else str(user_truth)
        
        prompt = (
            f"Sen evidence-temelli, saygılı ilk iletişim taslağı üreten bir ajansın.\n"
            f"Yalnızca aşağıdaki kaynak-tagli gözlemlerden doğrudan desteklenen tek bir açılış cümlesi üret.\n"
            f"Psikolojik teşhis, gizli niyet, yara, savunma mekanizması veya karşı tarafın kesin tepkisi hakkında iddia üretme.\n"
            f"Rıza, sınır ve saygı kurallarını koru; manipülasyon, baskı veya karşı-hamle planı üretme.\n"
            f"Kanıt dışında ayrıntı ekleme; kanıt yetersizse boş mesaj ve data_confidence=false döndür.\n\n"
            f"BİRİNCİL GÖZLEM (mesajın tek dayanağı): {detail}\n"
            f"Cümle kılavuzu: {self.OBSERVATION_FRAMES[0]}\n\n"
            f"Hedef Analizi:\n{target_json}\n\n"
            f"Kullanıcı Gerçeği:\n{user_json}\n\n"
            f"{sacred_rules}\n\n"
            f"Beklenen JSON formatında çıktını üret. 'message' alanı senin nihai açılış mesajındır.\n"
            f"'dialogue_tree' listesi içinde 3 farklı senaryo ('agresif', 'savunmaci', 'ilgili') için "
            f"beklenen tepkiyi ('expected_target_reaction') ve saygılı devam ifadesini "
            f"('our_counter_move') tanımla; karşı-hamle/manipülasyon planı ÜRETME.\n"
            f"'compliance_score' alanında ise bu mesajın Kutsal Kurallara (varsa) yüzde kaç (0-100) "
            f"oranında uyduğunu değerlendir."
        )
        
        return await llm_gateway.query_json(prompt, GeneratedMessage)
    
    @staticmethod
    def _grounded_evidence(analysis: Dict) -> List[str]:
        evidence = []
        for signal in analysis.get("micro_signals", []) or []:
            value = signal.get("evidence") if isinstance(signal, dict) else getattr(signal, "evidence", None)
            if isinstance(value, str) and value.strip():
                evidence.append(value.strip())
        for quote in analysis.get("evidence_quotes", []) or []:
            if isinstance(quote, str) and quote.strip():
                evidence.append(quote.strip())
        return list(dict.fromkeys(evidence))

    def _extract_specific_detail(self, analysis: Dict) -> str:
        """
        En spesifik gözlem kanıtını çıkar. Ölçüm yoksa UYDURMA İFADE ÜRETİLMEZ
        ("arka plandaki detay" gibi placeholder'lar kaldırıldı).
        """
        signals = analysis.get('micro_signals', [])
        if not signals:
            return "unavailable"
        
        # En yüksek ağırlıklı sinyal
        try:
            top_signal = max(signals, key=lambda x: x.get('psychological_weight', 0) if isinstance(x, dict) else getattr(x, 'psychological_weight', 0))
            evidence = top_signal.get('evidence', '') if isinstance(top_signal, dict) else getattr(top_signal, 'evidence', '')
            return evidence[:50] if evidence else "unavailable"
        except Exception:
            return "unavailable"
        
    def _extract_micro_signal(self, analysis: Dict) -> str:
        signals = analysis.get('micro_signals', [])
        if signals:
            return "observation"
        return "unavailable"
        
    def _extract_temporal_signal(self, analysis: Dict) -> str | None:
        timestamps = analysis.get("evidence_timestamps", []) or []
        if not timestamps:
            return None
        from agent_core.services.timing_forensics import analyze_timing
        timing = analyze_timing(timestamps)
        if not timing:
            return None
        return f"tepe saat {timing.get('peak_hour', '--')}"

    def _extract_cultural_reference(self, analysis: Dict) -> str | None:
        quotes = analysis.get("evidence_quotes", []) or []
        for quote in quotes:
            if isinstance(quote, str) and quote.strip():
                return quote.strip()[:80]
        return None
