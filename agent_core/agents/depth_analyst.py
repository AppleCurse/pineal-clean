from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict
import json

class DepthFinding(BaseModel):
    topic: str
    observation: str
    evidence_quotes: List[str] = []
    confidence_note: str = ""
    model_config = ConfigDict(extra="allow")

class DepthReport(BaseModel):
    reality_index: float  # 0.0 - 1.0 (Görünen hayatın kanıtla desteklenen oranı)
    reality_rationale: str
    reality_findings: List[DepthFinding] = []
    contradictions: List[DepthFinding] = []
    state_drift: Optional[str] = None
    timing_pattern: Optional[str] = None
    essence_one_liner: str
    follower_audit_summary: Optional[str] = None
    quote_guard: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(extra="allow")

class DepthAnalyst:
    """
    P1 + P7 + P8 Derinlik ve Gerçeklik Analisti.
    Görevi: Form doldurmak değil; kanıtları masaya yatırıp sahnelenen vitrin ile
    sızan gerçeklik arasındaki çelişkileri, şişirmeleri ve zaman sürüklenmesini çıkarmaktır.
    """
    def __init__(self, llm_gateway):
        self.llm_gateway = llm_gateway

    async def execute(self, input_data, memory, llm_gateway):
        """Standard agent interface wrapper."""
        evidence_chain = getattr(memory, "evidence_chain", []) if memory else input_data.get("evidence_chain", [])
        return await self.analyze(input_data, evidence_chain)

    async def analyze(self, input_data: Dict[str, Any], evidence_chain: List[Dict[str, Any]]) -> DepthReport:
        tp = input_data.get("target_profile", {})
        visual = input_data.get("visual_evidence", {})
        audit = input_data.get("follower_audit", {})
        timing = input_data.get("timing_forensics", {})
        
        prompt = (
            "Sen PINEAL 3.0 Baş Adli Psikoloji ve Gerçeklik Analistisin (Depth Analyst).\n"
            "GÖREVİN FORM DOLDURMAK VEYA YÜZEYSEL ETİKET BASMAK DEĞİLDİR.\n"
            "Aşağıdaki somut kanıtları masaya yatırıp ŞU SORULARI CEVAPLAYACAKSIN:\n\n"
            "1. GERÇEKLİK ENDEKSİ (Reality Index 0.0 - 1.0): Bu profilde sergilenen hayatın gerçekte yaşanma oranı nedir?\n"
            "   (Örn: Tek bir yat tatilini 12 farklı post olarak paylaşma, mevsim çelişkisi, şirketi olup ürün/üretim göstermeme vb.)\n"
            "2. ÇELİŞKİLER (Contradictions): Sahnelenen vitrin ile sızan gerçek arasındaki çelişkiler nelerdir?\n"
            "3. STATE DRIFT (Durum Sürüklenmesi): Görsellerde ve saatlerde zamanla yorgunluk/yıpranma veya yalnızlık kayması var mı?\n"
            "4. TEK CÜMLELİK ÖZ: Bu insanın en çıplak psikolojik röntgeni.\n\n"
            "KURALLAR:\n"
            "- Her bulgu ve çelişki İÇİN 'evidence_quotes' alanına KAYNAK METİNDEN BİREBİR ALINTI KOYMAK ZORUNDASIN.\n"
            "- Alıntısız veya uydurma olan tespitler kod tabanlı QuoteGuard tarafından imha edilecektir.\n\n"
            f"HEDEF PROFİL: {json.dumps(tp, ensure_ascii=False)}\n"
            f"GÖRSEL KANITLAR: {json.dumps(visual, ensure_ascii=False)}\n"
            f"TAKİPÇİ DENETİMİ (P9): {json.dumps(audit, ensure_ascii=False)}\n"
            f"ZAMAN FORENSİĞİ (Saatler): {json.dumps(timing, ensure_ascii=False)}\n"
        )

        try:
            report: DepthReport = await self.llm_gateway.query_json_chain(
                prompt, DepthReport, task="depth", agent_name="depth_analyst"
            )
            # QuoteGuard ile alıntı kontrolü ve sahte tespit temizliği
            from agent_core.services.quote_guard import guard_report
            rep_dict = report.model_dump()
            cleaned_dict, stats = guard_report(rep_dict, input_data)
            cleaned_dict["quote_guard"] = stats
            return DepthReport(**cleaned_dict)
        except Exception:
            # Fallback
            return DepthReport(
                reality_index=0.0,
                reality_rationale="",
                reality_findings=[],
                contradictions=[],
                essence_one_liner="",
                data_confidence=False,
                fallback_reason="llm_unavailable"
            )
