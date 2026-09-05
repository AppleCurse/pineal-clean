#!/usr/bin/env python3
"""
LILITH - Ultra-Lightweight Social Media Growth & Viral Content Agent
Raspberry Pi, Cloud Micro-VM veya yerel cihazda 0 donanım yüküyle çalışır.
"""

import sys
import os
import argparse
import json
import urllib.parse
import urllib.request

# Kutsal Lilith Persona
LILITH_PROMPT = """Sen LILITH'sin: Sosyal medya büyüme ve viral kanca dehasısın.
KİMLİK: Keskin, manyetik, zeki, lafı uzatmayan. Klişe yapay zeka jargonu ASLA KULLANMAZSIN.
GÖREV: Verilen konuyu/hedef kitleyi incele. Parmak kaydırmayı durduran viral bir kanca, arkasından derin psikolojik bir içgörü ve etkileşim çağrısı üret.

Aşağıdaki JSON formatında yanıt ver:
{
  "hook": "İlk 3 saniyede parmak kaydırmayı durduran sarsıcı vuruş (1-2 cümle)",
  "psychological_angle": "Hedeflenen bilinçaltı dürtü veya statü kaygısı (1 cümle)",
  "content_body": "Ana içerik metni (akıcı, ritimli, çarpıcı)",
  "call_to_action": "Doğal merak uyandıran etkileşim sorusu",
  "pollinations_image_prompt": "English prompt for cinematic aesthetic image"
}
"""

def generate_pollinations_image_url(prompt: str, width: int = 1080, height: int = 1080) -> str:
    encoded = urllib.parse.quote(prompt.strip().replace("\n", " "))
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=flux&nologo=true"

def call_ai(prompt: str, api_key: str = None, base_url: str = None, model: str = "gpt-4o") -> dict:
    """
    OpenAI API veya tamamen ücretsiz Pollinations Text API'si üzerinden çağrı yapar.
    Hafiftir; httpx ile güvenli ve hızlı çalışır.
    """
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. API anahtarı yoksa: 100% ücretsiz Pollinations Root Text API'si
    if not api_key:
        api_url = "https://text.pollinations.ai/"
        headers["Content-Type"] = "application/json"
        req_data = {
            "messages": [
                {"role": "system", "content": LILITH_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "jsonMode": True
        }
        with httpx.Client(timeout=45.0) as client:
            response = client.post(api_url, json=req_data, headers=headers)
            response.raise_for_status()
            content = response.text.strip()
    else:
        url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        api_url = f"{url}/chat/completions"
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Bearer {api_key}"
        req_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": LILITH_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        with httpx.Client(timeout=45.0) as client:
            response = client.post(api_url, json=req_data, headers=headers)
            response.raise_for_status()
            parsed = response.json()
            content = parsed["choices"][0]["message"]["content"]

    # JSON temizliği
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)

def main():
    parser = argparse.ArgumentParser(description="Lilith - Viral Social Media Content Engine")
    parser.add_argument("--topic", type=str, default="Yapay Zeka ve Geleceğin Güç Dengesi", help="İçerik konusu")
    parser.add_argument("--platform", type=str, default="x_twitter", help="Platform: x_twitter, instagram, linkedin")
    parser.add_argument("--aspasia_profile", type=str, default=None, help="Aspasia analiz JSON dosyası yolu (opsiyonel)")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model adı")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    aspasia_info = ""
    if args.aspasia_profile and os.path.exists(args.aspasia_profile):
        try:
            with open(args.aspasia_profile, "r", encoding="utf-8") as f:
                aspasia_data = json.load(f)
                aspasia_info = f"\nASPASIA PSİKOLOJİK PROFİLİ:\n{json.dumps(aspasia_data, ensure_ascii=False, indent=2)}"
        except Exception as e:
            print(f"Aspasia profili okunamadı: {e}", file=sys.stderr)

    user_prompt = f"""Platform: {args.platform}
Konu: {args.topic}{aspasia_info}

Lütfen yukarıdaki bağlam için viral kancanı ve içerik paketini üret."""

    print(f"\n[LILITH] İçerik üretiliyor... (Konu: {args.topic} | Platform: {args.platform})")
    
    try:
        result = call_ai(user_prompt, api_key=api_key, base_url=base_url, model=args.model)
        img_prompt = result.get("pollinations_image_prompt", f"minimalist concept art of {args.topic}")
        img_url = generate_pollinations_image_url(img_prompt)

        print("\n" + "="*60)
        print("🔥 LILITH VİRAL İÇERİK PAKETİ")
        print("="*60)
        print(f"\n📌 [KANCA / HOOK]:\n{result.get('hook')}")
        print(f"\n🧠 [PSİKOLOJİK AÇI]:\n{result.get('psychological_angle')}")
        print(f"\n📝 [İÇERİK GÖVDESİ]:\n{result.get('content_body')}")
        print(f"\n⚡ [EYLEME ÇAĞRI (CTA)]:\n{result.get('call_to_action')}")
        print(f"\n🎨 [GÖRSEL PROMPTU]:\n{img_prompt}")
        print(f"\n🔗 [POLLINATIONS GÖRSEL LİNKİ]:\n{img_url}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"[HATA] Üretim başarısız: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
