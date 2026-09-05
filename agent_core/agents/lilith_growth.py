import logging
import urllib.parse
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict
from agent_core.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

LILITH_SYSTEM_PROMPT = """Sen LILITH'sin: Sosyal medya büyüme, viral kanca ve kitle psikolojisi ustası.

KİMLİK:
- Manyetik, keskin, zeki ve sarsıcı bir tona sahipsin.
- Klişe yapay zeka jargonu ("günümüzün hızla değişen dünyasında", "derinlemesine inceleyelim", "şüphesiz ki") ASLA KULLANMAZSIN.
- İnsanların egolarını, bastırılmış arzularını, statü kaygılarını ve bilişsel çelişkilerini doğrudan yakalarsın.
- Her cümlen bir ritme sahiptir; parmak kaydırmayı (scroll) anında durdurursun.

METODOLOJİ (Kutsal Üçgen):
1. Bilişsel Kanca (Hook): Okuyucunun inandığı bir yanılgıyı sarsan veya bastırdığı bir gerçeği yüzüne vuran ilk 1-2 cümle.
2. Gerilim & Değer (Body): Aspasia'nın tespit ettiği sürtünme ve tutku noktalarını harmanlayan, ezber bozan içgörü.
3. Eyleme Çağrı (CTA): Yalvarmayan, merak veya statü tetikleyen doğal kapanış.

GÖRSEL VİZYON:
- Postun yarattığı psikolojik tansiyonu görselleştirecek, sinematik, minimalist veya çarpıcı bir Pollinations görsel promptu üretirsin.
"""

class LilithContentPackage(BaseModel):
    """Lilith tarafından üretilen viral içerik paketi."""
    platform: str = "x_twitter"  # x_twitter, instagram, linkedin, threads
    hook: str
    psychological_angle: str
    content_body: str
    call_to_action: str
    pollinations_image_prompt: str
    pollinations_image_url: str
    confidence: float = 0.0
    data_confidence: bool = False
    fallback_reason: Optional[str] = None

    model_config = ConfigDict(extra="allow")

class LilithGrowthAgent:
    """
    Aspasia'nın 360° insan analizini (tutkular, sürtünmeler, bilişsel üslup)
    viral sosyal medya içeriklerine ve kitle büyütme stratejisine dönüştüren ajan.
    Tüy kadar hafif, sunucusuz ve Raspberry Pi'de bile sıfır yükle çalışır.
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm_gateway = llm_gateway or LLMGateway()

    def build_pollinations_url(
        self,
        prompt: str,
        width: int = 1080,
        height: int = 1080,
        model: str = "flux"
    ) -> str:
        """Pollinations.ai üzerinden 0-token, API key'siz anında görsel URL'i oluşturur."""
        clean_prompt = prompt.strip().replace("\n", " ")
        encoded = urllib.parse.quote(clean_prompt)
        return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model={model}&nologo=true"

    async def execute(self, payload: Dict[str, Any]) -> LilithContentPackage:
        """
        Aspasia profilini veya doğrudan konuyu alıp viral içerik üretir.
        """
        topic = payload.get("topic", "")
        platform = payload.get("platform", "x_twitter")
        
        # Aspasia profil bileşenleri
        target_profile = payload.get("target_profile", {})
        friction = payload.get("friction_profile", {})
        passion = payload.get("passion_profile", {})
        cognitive = payload.get("cognitive_style", {})

        # Sürtünme ve tutku sinyallerini derle
        frictions_text = ", ".join(friction.get("sensitivities", []) + friction.get("stress_triggers", []))
        passions_text = ", ".join(passion.get("core_passions", []) + passion.get("energizing_topics", []))
        tone_pref = cognitive.get("communication_tone", "doğrudan")

        has_profile = bool(frictions_text or passions_text or target_profile)

        context_block = f"""
Hedef Kitle / Konu: {topic or 'Belirtilmedi'}
Platform: {platform}
Tercih Edilen Üslup: {tone_pref}
Hassasiyetler & Sürtünme Noktaları (Aspasia): {frictions_text or 'Genel kitle psikolojisi'}
Tutku & Enerji Alanları (Aspasia): {passions_text or 'Yüksek merak alanları'}
"""

        prompt = f"""{LILITH_SYSTEM_PROMPT}

Aşağıdaki verileri incele ve bu hedef kitleyi manyetik biçimde çekecek, etkileşim patlaması yaratacak bir içerik paketi üret.

GİRDİ ANALİZİ:
{context_block}

Gereksinimler:
1. 'hook': İlk 3 saniyede parmak kaydırmayı durduran vuruş (1-2 cümle).
2. 'psychological_angle': Hangi psikolojik dürtüyü/korkuyu/arzuyu hedeflediğinin 1 cümlelik teknik açıklaması.
3. 'content_body': Ana gövde (X için 2-3 tweetlik akış veya tek çarpıcı metin; Instagram/LinkedIn için paragraf ritimli metin).
4. 'call_to_action': Doğal, merak uyandıran etkileşim sorusu.
5. 'pollinations_image_prompt': İngilizce, son derece estetik, sinematik, minimalist görsel tarif (örn: 'cinematic 35mm photography of a person standing at the edge of a brutalist architecture balcony, moody lighting, dark aesthetic, 8k').

Aşağıdaki JSON şemasına BİREBİR uygun yanıt ver:
{{
  "hook": "...",
  "psychological_angle": "...",
  "content_body": "...",
  "call_to_action": "...",
  "pollinations_image_prompt": "...",
  "confidence": 0.95
}}
"""

        try:
            res = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            raw = res.choices[0].message.content or "{}"
            import json
            data = json.loads(raw)

            img_prompt = data.get("pollinations_image_prompt", f"aesthetic minimalist editorial photo for {topic}")
            img_url = self.build_pollinations_url(img_prompt)

            return LilithContentPackage(
                platform=platform,
                hook=data.get("hook", ""),
                psychological_angle=data.get("psychological_angle", ""),
                content_body=data.get("content_body", ""),
                call_to_action=data.get("call_to_action", ""),
                pollinations_image_prompt=img_prompt,
                pollinations_image_url=img_url,
                confidence=float(data.get("confidence", 0.9)),
                data_confidence=has_profile,
                fallback_reason=None
            )
        except Exception as e:
            logger.error(f"Lilith içerik üretimi sırasında hata: {e}")
            fallback_prompt = f"minimalist dark aesthetic concept art of {topic or 'insight'}"
            return LilithContentPackage(
                platform=platform,
                hook=f"Çoğu insanın göremediği gerçek: {topic or 'başarı'} hakkında bildiklerinizi unutun.",
                psychological_angle="Bilişsel çelişki ve statü sorgulaması",
                content_body="Gürültünün ortasında sinyali yakalamak için önce neye neden tepki verdiğinizi anlamanız gerekir.",
                call_to_action="Sizce en büyük yanılgı nerede?",
                pollinations_image_prompt=fallback_prompt,
                pollinations_image_url=self.build_pollinations_url(fallback_prompt),
                confidence=0.5,
                data_confidence=False,
                fallback_reason=f"error: {str(e)}"
            )
