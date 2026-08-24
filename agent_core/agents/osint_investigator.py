import logging
import aiohttp
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

class OsintProfile(BaseModel):
    connected_emails: list[str] = []
    connected_phones: list[str] = []
    associated_platforms: list[str] = []
    digital_footprint_score: float = 0.0  # 0.0 (hayalet) - 1.0 (çok aktif)
    dark_web_hits: int = 0
    confidence: float = 1.0
    data_confidence: bool = True          # False → LLM kullanılamadı veya API yoktu
    fallback_reason: Optional[str] = None # "no_api_key" | "llm_unavailable" | None

    model_config = ConfigDict(extra="allow")

class OsintInvestigatorAgent:
    """
    SOTA (State of the Art) OSINT katmanı.
    osint.industries / SpiderFoot API'leri üzerinden hedefin kullanıcı adını
    kullanarak dijital ayak izini (e-posta, telefon, diğer platformlar) çıkarır.
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()
        # osint.industries API key vault'tan veya env'den alınabilir.
        self.osint_api_key = os.getenv("OSINT_INDUSTRIES_KEY", None)

    def _get_alf_headers(self) -> Dict[str, str]:
        import random
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }
        if self.osint_api_key:
            headers["api-key"] = self.osint_api_key
        return headers

    async def execute(self, payload: Dict[str, Any]) -> OsintProfile:
        target = payload.get("target_profile", {})
        username = target.get("username", "")

        if not username:
            return OsintProfile(confidence=1.0)

        clean_username = username.lstrip("@")
        
        # Gerçek bir API anahtarı yoksa Mock veri dön (Testlerin kırılmaması ve 
        # API maliyeti oluşturmaması için SOTA simülasyonu)
        if not self.osint_api_key:
            logger.info(f"[OSINT] API anahtarı bulunamadı, '{clean_username}' için analiz atlanıyor (Fallback mode).")
            # Return empty/unknown state due to lack of API key, avoiding LLM hallucinations.
            return OsintProfile(
                connected_emails=[],
                connected_phones=[],
                associated_platforms=[],
                digital_footprint_score=0.0,
                dark_web_hits=0,
                confidence=0.0,
                data_confidence=False
            )
        else:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = self._get_alf_headers()
                    async with session.get(f"https://api.osint.industries/v1/user/{clean_username}", headers=headers, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            emails = data.get("emails", [])
                            phones = data.get("phones", [])
                            platforms = data.get("platforms", [])
                            return OsintProfile(
                                connected_emails=emails,
                                connected_phones=phones,
                                associated_platforms=platforms,
                                confidence=0.9,
                                data_confidence=True
                            )
                        else:
                            logger.warning(f"[OSINT] Canlı API hatası: HTTP {resp.status} - {await resp.text()}")
                            return OsintProfile(confidence=1.0, data_confidence=False, fallback_reason="api_error")
            except Exception as e:
                logger.warning(f"[OSINT] Canlı API bağlantı hatası: {e}")
                return OsintProfile(confidence=1.0, data_confidence=False, fallback_reason="api_error")
