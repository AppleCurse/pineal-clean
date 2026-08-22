import httpx
import json
import os
from typing import Dict, Optional, Any

class ClaudeAnalyzer:
    """
    Gerçek Claude 3.5 Sonnet bağlantısı.
    Şablon YOK. Her analiz canlı ve özel.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.url = "https://api.anthropic.com/v1/messages"
    
    async def analyze_instagram_profile(self, 
                                        username: str,
                                        bio: str, 
                                        posts: list,
                                        captions: list) -> Dict:
        """
        Gerçek veriyi Claude'a gönder, gerçek analiz al.
        """
        
        prompt = f"""
        Instagram hedef analizi:
        
        Kullanıcı adı: @{username}
        Bio: "{bio}"
        
        Son paylaşımlar:
        {json.dumps(posts[:5], ensure_ascii=False)}
        
        Görevler:
        1. Bu kişinin gerçekten ne istediğini tespit et (yüzeydeki değil, derin arzu)
        2. En son paylaşımdaki spesifik detayı bul (bir kitap, şarkı, mekan, duygu)
        3. Bağlanma stili: "anxious", "avoidant" veya "secure"
        4. Core Wound (Çekirdek Yara): "abandonment", "shame", "betrayal" veya "unlovability"
        5. Exploitability (Sömürülebilirlik/Etkilenebilirlik): 0.0 ile 1.0 arası bir ondalık sayı.
        6. Dark Triad: Machiavellianism, Narcissism, Psychopathy (hepsi 0.0-1.0 arası)
        
        Çıktı KESİNLİKLE GEÇERLİ BİR JSON OLMALIDIR. Markdown (```json) bloğu KULLANMA.
        Format:
        {{
            "real_desire": "...",
            "specific_detail": "...", 
            "attachment_style": "...",
            "core_wound": "...",
            "exploitability": 0.85,
            "dark_triad": {{
                "machiavellianism": 0.5,
                "narcissism": 0.7,
                "psychopathy": 0.2
            }}
        }}
        """
        
        if not self.api_key:
            return self._get_fallback_analysis(username)
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 1000,
                        "temperature": 0.8,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    print(f"Claude API Error: {response.status_code} - {response.text}")
                    return self._get_fallback_analysis(username)
                    
                result = response.json()
                content = result['content'][0]['text']
                
                # Temizle
                content = content.replace('```json', '').replace('```', '').strip()
                
                # JSON parse et
                return json.loads(content)
        except Exception as e:
            print(f"Claude Exception: {str(e)}")
            return self._get_fallback_analysis(username)
            
    async def claude_request(self, prompt: str) -> str:
        if not self.api_key:
            return "API Key eksik. Kasa kilidini açmalısınız."
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 1000,
                        "temperature": 0.8,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.json()['content'][0]['text']
                return f"Hata: {response.status_code}"
        except Exception as e:
            return f"İstisna: {str(e)}"
            
    def _get_fallback_analysis(self, username: str) -> Dict:
        """API yokken sistemin çökmemesi için fallback, ama logda belli olsun."""
        return {
            "real_desire": "API YOK - Fallback Data",
            "specific_detail": "API YOK - Fallback Data", 
            "attachment_style": "secure",
            "core_wound": "abandonment",
            "exploitability": 0.5,
            "dark_triad": {
                "machiavellianism": 0.5,
                "narcissism": 0.5,
                "psychopathy": 0.5
            },
            "error": "No API Key provided"
        }
