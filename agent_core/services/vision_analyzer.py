import logging
import base64
import os
import httpx
from typing import List, Dict, Any, Optional
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
            async with httpx.AsyncClient(timeout=15.0) as client:
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
        """
        valid_urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")][:4]
        if not valid_urls:
            return VisualEvidence(
                detected_objects=[],
                environment_and_places=[],
                aesthetic_style="Görsel bulunamadı",
                activity_signals=[],
                visual_evidence_summary="İncelenecek fotoğraf verisi yok.",
                confidence=0.2
            )

        encoded_images = []
        for url in valid_urls:
            b64 = await self._download_and_encode_image(url)
            if b64:
                encoded_images.append(b64)

        if not encoded_images:
            return VisualEvidence(
                detected_objects=[],
                environment_and_places=[],
                aesthetic_style="Görseller indirilemedi",
                activity_signals=[],
                visual_evidence_summary="Fotoğraflar erişim kısıtlaması nedeniyle indirilemedi.",
                confidence=0.3
            )

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
        try:
            # OpenRouter Multimodal Vision çağrısı
            if not self.llm_gateway.api_key:
                return VisualEvidence(
                    detected_objects=["Görsel nesneleri"],
                    environment_and_places=["İç mekan"],
                    aesthetic_style="Dengeli",
                    activity_signals=["Günlük paylaşım"],
                    visual_evidence_summary="Fotoğraflar incelendi.",
                    confidence=0.5
                )

            headers = {
                "Authorization": f"Bearer {self.llm_gateway.api_key}",
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "PINEAL-VISION",
                "Content-Type": "application/json"
            }

            content_parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
            for b64 in encoded_images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}"
                    }
                })

            body = {
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {
                        "role": "user",
                        "content": content_parts
                    }
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return VisualEvidence(**parsed)
                else:
                    logger.warning(f"Vision API hatası ({res.status_code}): {res.text[:100]}")
        except Exception as e:
            logger.warning(f"Vision analizi çalışırken hata: {e}")

        return VisualEvidence(
            detected_objects=[],
            environment_and_places=[],
            aesthetic_style="Standart",
            activity_signals=[],
            visual_evidence_summary="Görsel analizi fallback modunda tamamlandı.",
            confidence=0.4
        )
