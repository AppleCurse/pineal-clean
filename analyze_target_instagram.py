import asyncio
import json
import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright
from agent_core.task_executor import PinealExecutor
from agent_core.domain.memory_models import TaskSnapshot
from agent_core.scraper.instagram_ghost import InstagramGhostScraper

async def main():
    target_url = "https://www.instagram.com/cemiyettesimyaci/"
    username = "cemiyettesimyaci"

    print("="*65)
    print(f"PINEAL 3.0: CANLI INSTAGRAM HEDEF ANALİZİ: @{username}")
    print("="*65)

    # 1. Kasa Yüklemesi
    executor = PinealExecutor(log_callback=lambda lvl, msg: print(f"[{lvl}] {msg}"))
    vault_file = ".pineal_vault.json"
    api_key = None
    if os.path.exists(vault_file):
        with open(vault_file, "r", encoding="utf-8") as f:
            v = json.load(f)
            api_key = v.get("api_key")
            if api_key:
                executor.llm_gateway.set_key(api_key)
                print(f"[KASA] LLM API Anahtarı yüklendi: {api_key[:12]}...")
            tavily = v.get("tavily_key")
            serpapi = v.get("serpapi_key")
            exa = v.get("exa_key")
            if tavily or serpapi or exa:
                executor.search_engine.set_keys(tavily=tavily, serpapi=serpapi, exa=exa)
                print("[KASA] Arama Motoru Anahtarları yüklendi.")

    # 2. Hayalet Tarayıcı ile Canlı Kazıma
    print(f"\n[1/3] Hayalet Tarayıcı Başlatılıyor (System Chrome)...")
    scraped_bio = ""
    scraped_posts = []
    scraped_followers = None
    scraped_following = None
    full_name = ""
    is_private = False

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    launch_kwargs = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
    if os.path.exists(chrome_path):
        launch_kwargs["executable_path"] = chrome_path

    try:
        from playwright_stealth import Stealth
        stealth_engine = Stealth()
    except Exception:
        stealth_engine = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="tr-TR"
        )
        page = await ctx.new_page()
        if stealth_engine:
            await stealth_engine.apply_stealth_async(page)

        print(f" -> {target_url} adresine gidiliyor...")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(3)
            html = await page.content()
            
            # Meta tags extraction
            og_desc_match = re.search(r'<meta property="og:description" content="([^"]*)"', html)
            if not og_desc_match:
                og_desc_match = re.search(r'<meta content="([^"]*)" property="og:description"', html)
            if not og_desc_match:
                og_desc_match = re.search(r'<meta name="description" content="([^"]*)"', html)
            if not og_desc_match:
                og_desc_match = re.search(r'<meta content="([^"]*)" name="description"', html)

            if og_desc_match:
                og_desc = og_desc_match.group(1)
                print(f" -> Meta Açıklama: {og_desc}")
                
                # Takipçi / Takip / Gönderi regex
                fol_m = re.search(r'([\d\.,KMkm]+)\s*(?:Takipçi|Followers)', og_desc, re.IGNORECASE)
                if fol_m: scraped_followers = fol_m.group(1)
                fing_m = re.search(r'([\d\.,KMkm]+)\s*(?:Takip|Following)', og_desc, re.IGNORECASE)
                if fing_m: scraped_following = fing_m.group(1)

            og_title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            if og_title_match:
                print(f" -> Meta Başlık: {og_title_match.group(1)}")
                name_m = re.search(r'^(.*?)\s*\(@', og_title_match.group(1))
                if name_m: full_name = name_m.group(1).strip()

            # Bio çıkarma
            bio_match = re.search(r'<meta content="[^"]*Instagram\'da [^:]*:\s*&quot;([^&]*)&quot;" name="description"', html)
            if not bio_match:
                bio_match = re.search(r'name="description"\s+content="[^"]*:\s*&quot;([^&]*)&quot;"', html)
            if bio_match:
                scraped_bio = bio_match.group(1).strip()
            elif og_desc_match and "photos and videos" not in og_desc_match.group(1).lower():
                # Bio direct in meta
                desc_text = og_desc_match.group(1)
                if " - " in desc_text:
                    scraped_bio = desc_text.split(" - ", 1)[-1].strip()

            # Post captionları
            captions = re.findall(r'"text":"([^"\\]*(?:\\.[^"\\]*)*)"', html)
            for c in captions:
                clean_c = c.encode().decode('unicode-escape', errors='ignore').strip()
                if len(clean_c) > 10 and clean_c not in scraped_posts and not clean_c.startswith("http"):
                    scraped_posts.append(clean_c)

            print(f" -> Çekilen İsim: {full_name or 'Yok'}")
            print(f" -> Çekilen Takipçi: {scraped_followers or 'Yok'} | Takip: {scraped_following or 'Yok'}")
            print(f" -> Çekilen Biyografi: {scraped_bio or 'Boş / Kapalı'}")
            print(f" -> Çekilen Gönderi Metinleri: {len(scraped_posts)} adet")

        except Exception as e:
            print(f"[UYARI] Tarayıcı kazıma sırasında hata: {e}")
        finally:
            await browser.close()

    # 3. Profil Hazırlama & 360° Analiz
    print("\n[2/3] 360° Analiz Yükü Oluşturuluyor...")
    
    target_payload = {
        "username": f"@{username}",
        "full_name": full_name or username,
        "bio": scraped_bio or f"Instagram hedef profili @{username}",
        "posts": scraped_posts[:10],
        "followers": scraped_followers,
        "following": scraped_following
    }

    user_payload = {
        "bio": "Analitik felsefe, edebiyat ve derin insan iletişimi araştırmacısı.",
        "posts": [
            "Yüzeysel kalıpların ardındaki hakikati aramak.",
            "Kelimelerin ağırlığı ve anlamı."
        ],
        "private_rituals": ["gece okumaları", "felsefi notlar", "derin müzik dinleme"],
        "late_night_playlist": ["derin enstrümantal", "klasik", "ambient"],
        "secret_envies": ["hakiki ve yapıcı bir diyalog kurabilmek"],
        "authenticity_score": 0.90
    }

    pipeline_input = {
        "target_profile": target_payload,
        "user_profile": user_payload,
        "sacred_rules": "Ucuz astroloji klişelerinden ve dalkavukluktan kesinlikle kaçın. Hedefin gerçek kimliğini, tutkularını ve sınırlarını saygıyla analiz et."
    }

    print("\n[3/3] PINEAL 3.0 Bütüncül Karar Motoru Çalıştırılıyor...")
    result: TaskSnapshot = await executor.execute_task(pipeline_input, task_id=f"cemiyet_{username}")

    print("\n" + "="*65)
    print("ANALİZ VE ÇÖZÜMLEME RAPORU")
    print("="*65)
    print(f"Durum: {result.status}")
    print(f"Tamamlanan Ajanlar: {', '.join(result.completed_agents)}")
    if result.halted_reason:
        print(f"Durdurma Sebebi: {result.halted_reason}")

    hp = result.holistic_profile
    if hp:
        print("\n🧠 360° BÜTÜNCÜL İNSAN PROFİLİ:")
        
        if hp.passions:
            print("\n✨ TUTKULAR VE NEŞE:")
            print(f"  • Ana Tutkular: {hp.passions.core_passions}")
            print(f"  • Enerji Veren Konular: {hp.passions.energizing_topics}")
            print(f"  • Akış Tetikleyicileri: {hp.passions.flow_triggers}")
            print(f"  • Coşku Düzeyi: {hp.passions.sentiment_polarity}")
            print(f"  • Kanıt Alıntıları: {hp.passions.evidence_quotes}")

        if hp.frictions:
            print("\n🛡️ HASSASİYETLER VE SINIRLAR:")
            print(f"  • Hassasiyetler: {hp.frictions.sensitivities}")
            print(f"  • Stres/Yorulma Tetikleyicileri: {hp.frictions.stress_triggers}")
            print(f"  • İletişim Sınırları: {hp.frictions.boundary_signals}")
            print(f"  • Kanıt Alıntıları: {hp.frictions.evidence_quotes}")

        if hp.cognitive:
            print("\n💬 BİLİŞSEL VE İLETİŞİM ÜSLUBU:")
            print(f"  • İletişim Tonu: {hp.cognitive.communication_tone}")
            print(f"  • Karmaşıklık: {hp.cognitive.complexity_level}")
            print(f"  • Mizah Tarzı: {hp.cognitive.humor_style}")
            print(f"  • Sosyal Yaklaşım: {hp.cognitive.social_orientation}")

        if hp.bridge:
            print("\n🌿 SAHİCİ İLETİŞİM KÖPRÜSÜ (ÖNERİLEN İLK TEMAS):")
            print(f"  • Rezonans Skoru: %{hp.bridge.resonance_score * 100:.1f}")
            print(f"  • Ortak Tutkular: {hp.bridge.shared_passions}")
            print(f"  • Tamamlayıcı Perspektifler: {hp.bridge.complementary_perspectives}")
            print(f"  • Önerilen Açılış Konusu: {hp.bridge.authentic_opening_topic}")
            print(f"  • Stratejik Gerekçe: {hp.bridge.conversation_starter_rationale}")
            print(f"\n  👉 ÖNERİLEN SAHİCİ İLK MESAJ:\n  \"{hp.bridge.suggested_opening_message}\"")

    print("="*65)

if __name__ == "__main__":
    asyncio.run(main())
