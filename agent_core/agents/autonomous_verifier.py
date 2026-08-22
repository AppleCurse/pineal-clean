from pydantic import BaseModel, ConfigDict
from typing import Dict, List

class Claim(BaseModel):
    claim_text: str
    category: str = "genel"

class VerificationResult(BaseModel):
    claim_text: str
    truth_status: str
    evidence_url: str = ""
    contradiction_detail: str = ""

class VerifierReport(BaseModel):
    verifications: List[VerificationResult] = []
    overall_authenticity_score: float = 0.0
    status: str = "VERIFIED"

    model_config = ConfigDict(extra="forbid")

class AutonomousVerifier:
    """Hedef profilindeki doğrulanabilir iddiaları dış kaynaklarla teyit eder."""

    def __init__(self, search_engine):
        self.search_engine = search_engine

    async def execute(self, input_data: Dict, memory, llm_gateway) -> VerifierReport:
        target_profile = input_data.get('target_profile', {})
        bio = target_profile.get('bio', '')

        if not bio or not self.search_engine.tavily_key:
            return VerifierReport(
                verifications=[],
                overall_authenticity_score=0.0,
                status="UNVERIFIED",
            )

        claim_prompt = (
            f"Hedefin biyografisi: '{bio}'\n"
            "Bu biyografide geçen doğrulanabilir, nesnel bilgileri (iş, unvan, okul, şirket vb.) çıkar.\n"
            "Örnek format: {\"claims\": [{\"claim_text\": \"Stratejist\", \"category\": \"meslek\"}]}\n"
            "Eğer teyit edilebilecek bir iddia yoksa {\"claims\": []} dön."
        )

        class ClaimList(BaseModel):
            claims: List[Claim] = []

        try:
            claim_data = await llm_gateway.query_json(claim_prompt, ClaimList, tier=2)
            claims_list = claim_data.claims if hasattr(claim_data, "claims") else []
        except Exception:
            claims_list = []

        if not claims_list:
            return VerifierReport(
                verifications=[],
                overall_authenticity_score=1.0,
                status="UNVERIFIED",
            )

        verifications = []
        for claim in claim_data.claims:
            query = claim.claim_text
            name = target_profile.get("name", "")
            if name:
                query = f"{name} {query}"

            results = await self.search_engine.search(query, num_results=2)
            if not results:
                verifications.append(VerificationResult(
                    claim_text=claim.claim_text,
                    truth_status="BİLİNMİYOR",
                    evidence_url="",
                    contradiction_detail="İnternette bu iddiayı doğrulayan / yalanlayan iz bulunamadı.",
                ))
                continue

            search_context = "\n".join([f"- Kaynak ({r.source_url}): {r.content}" for r in results])
            verify_prompt = (
                f"Hedefin İddiası: '{claim.claim_text}'\n\n"
                f"İnternet Arama Sonuçları:\n{search_context}\n\n"
                "Görevin: İnternet sonuçlarına bakarak bu iddianın doğru mu, abartılı mı, yoksa tamamen yalan mı olduğunu bulmak.\n"
                "Statü olarak SADECE şu kelimeleri kullanabilirsin: 'DOĞRULANDI', 'ÇELİŞKİLİ', 'YALAN', 'BİLİNMİYOR'.\n"
            )
            single_verification = await llm_gateway.query_json(verify_prompt, VerificationResult, tier=2)
            verifications.append(single_verification)

        total = len(verifications)
        if total == 0:
            return VerifierReport(
                verifications=[],
                overall_authenticity_score=0.0,
                status="UNVERIFIED",
            )

        lies = sum(1 for v in verifications if v.truth_status in ["YALAN", "ÇELİŞKİLİ"])
        score = max(0.0, 1.0 - (lies / total))
        status = "VERIFIED" if any(v.truth_status == "DOĞRULANDI" for v in verifications) else "UNVERIFIED"

        return VerifierReport(
            verifications=verifications,
            overall_authenticity_score=score,
            status=status,
        )
