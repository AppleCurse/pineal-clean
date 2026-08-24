import logging
import base64
import asyncio
import httpx
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

class VisualEvidence(BaseModel):
    """Görsellerden çıkarılan somut nesne, mekan ve estetik kanıtlar."""
    detected_objects: List[str] = []         # Kitaplar, fotoğraf makinesi, plak, bitkiler vb.
    environment_and_places: List[str] = []   # Loş oda, atölye, sahil, sergi salonu vb.
    aesthetic_style: str = ""                # Analog gren, monokrom, minimal, karanlık/loş vb.
    activity_signals: List[str] = []         # Gece çalışması, yalnız yürüyüş, müzik kaydı vb.
    visual_evidence_summary: str = ""        # 2-3 cümlelik somut görsel özet
    confidence: float = 1.0
    data_confidence: bool = True             # False → UNAVAILABLE (analiz yapılamadı)
    fallback_reason: Optional[str] = None    # llm_api_key_unavailable | image_download_failed | ...

    model_config = ConfigDict(extra="allow")

class VisionAnalyzer:
    """
    Instagram ve sosyal medya görsellerini çoklu modlu (Multimodal Vision)
    yapay zeka ile inceleyip somut nesne ve mekan kanıtları çıkaran servis.
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()

    async def _download_and_encode_image(self, image_url: str) -> Optional[str]:
        """Görseli indirip base64 formatına çevirir."""
        if not image_url or not image_url.startswith("http"):
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(image_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                })
                if resp.status_code == 200:
                    return base64.b64encode(resp.content).decode("utf-8")
        except Exception as e:
            logger.warning(f"Görsel indirilemedi ({image_url[:40]}...): {e}")
        return None

    async def analyze_images(self, image_urls: List[str], target_context: str = "") -> VisualEvidence:
        """
        Fotoğraf URL'lerini indirir ve Multimodal Vision modeliyle inceler.

        P0 SÖZLEŞMESİ:
        - Vision modeli yalnızca OPENROUTER_VISION_MODEL env'i ile belirlenir (hardcode yok).
        - Kimlik bilgisi yoksa veya analiz yapılamazsa UNAVAILABLE dönülür:
          boş kanıt + confidence=0.0 + data_confidence=False. Uydurma içerik üretilmez.

        S2 SÖZLEŞMESİ:
        - Çağrı doğrudan OpenRouter HTTP'si DEĞİL, LLMGateway.query üzerinden
          yapılır; LIVE_LLM_E2E kapısı, circuit breaker, retry ve provider
          politikası bu yolda da geçerlidir (bypass yok).
        """
        valid_urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")][:4]
        if not valid_urls:
            return self._unavailable("no_http_image_urls")

        # Parallel image download
        tasks = [self._download_and_encode_image(url) for url in valid_urls]
        results = await asyncio.gather(*tasks)

        encoded_images = [b64 for b64 in results if b64]

        if not encoded_images:
            return self._unavailable("image_download_failed")

        # Multimodal Vision Prompt
        prompt = f"""
Aşağıda hedefin Instagram profilinden çekilen {len(encoded_images)} adet fotoğrafın verisi sunulmaktadır.
Görevin, bu fotoğraflardaki SOMUT kanıtları, nesneleri, mekanları ve görsel atmosferi tespit etmektir.
Asla basmakalıp psikoloji uydurma. Sadece fotoğraflarda fiilen görünen nesneleri ve detayları yaz.

Hedef Bağlamı: "{target_context}"

Aşağıdaki JSON şemasına tam uygun yanıt ver:
{{
  "detected_objects": ["Fotoğraflarda fiilen görünen somut nesneler (ör: analog kamera, kitap, plak, seramik, kahve fincanı, mikrofon vb.)"],
  "environment_and_places": ["Fotoğrafların çekildiği mekanlar (ör: karanlık oda, stüdyo, orman, sahil, loş kafe vb.)"],
  "aesthetic_style": "Görsel tarz (ör: 35mm analog gren, desatüre monokrom, loş ışık, canlı minimal)",
  "activity_signals": ["Fotoğraflarda yapılan eylemler (ör: film banyosu, gece yürüyüşü, çizim, kayıt vb.)"],
  "visual_evidence_summary": "Fotoğraflardan çıkan somut ve net 2 cümlelik görsel kanıt özeti",
  "confidence": 0.90
}}
"""
        if not self.llm_gateway.api_key:
            return self._unavailable("llm_api_key_unavailable")

        # S2: çağrı LLMGateway üzerinden yapılır; LIVE_LLM_E2E kapısı,
        # circuit breaker, retry ve env-tabanlı vision modeli miras alınır.
        images = [f"data:image/jpeg;base64,{b64}" for b64 in encoded_images]
        try:
            raw = await self.llm_gateway.query(prompt, temperature=0.2, images=images)
            try:
                parsed = self.llm_gateway.extract_json(raw)
            except ValueError:
                # Tek tamir denemesi (query_json deseninin vision muadili)
                repair_prompt = (
                    "Önceki yanıtın geçerli bir JSON nesnesi değildi. "
                    "Yalnızca şu alanları içeren JSON döndür: "
                    "detected_objects (liste), environment_and_places (liste), "
                    "aesthetic_style (metin), activity_signals (liste), "
                    "visual_evidence_summary (metin), confidence (0-1 sayı). "
                    f"Bozuk yanıt: {raw[:200]}"
                )
                raw = await self.llm_gateway.query(repair_prompt, temperature=0.2, images=images)
                parsed = self.llm_gateway.extract_json(raw)
            return VisualEvidence(**parsed)
        except RuntimeError as exc:
            if "REAL_LLM_CALL_NOT_EXECUTED" in str(exc):
                # S2: canlı-çağrı kapısı kapalı — outbound provider çağrısı YOK.
                return self._unavailable("llm_live_gate_closed")
            logger.warning(f"Vision LLM çağrı hatası: {exc}")
            return self._unavailable("llm_unavailable")
        except Exception as exc:
            logger.warning(f"Vision analizi çalışırken hata: {exc}")
            return self._unavailable("vision_analysis_failed")

    @staticmethod
    def _unavailable(reason: str) -> VisualEvidence:
        """P0 SÖZLEŞMESİ: analiz yapılamadığında boş kanıt + confidence=0.0 döner."""
        return VisualEvidence(
            detected_objects=[],
            environment_and_places=[],
            aesthetic_style="",
            activity_signals=[],
            visual_evidence_summary="",
            confidence=0.0,
            data_confidence=False,
            fallback_reason=reason,
        )
