import random
import asyncio
from typing import Optional

class ZeigarnikEngine:
    """
    Tamamlanmamis gorevler beyni mesgul eder.
    Acik donguler (open loops) hedefi dusundurur.
    FAZ 3: LLM ile dinamik uretim — statik liste fallback.
    """

    # Fallback: LLM yoksa kullanilir
    OPEN_LOOP_PHRASES = [
        "Sana bir sey soyleyecektim ama... Belki baska zaman.",
        "Bu konuda daha fazlasi var ama simdi degil.",
        "O hikayenin devami var... Eger merak edersen.",
        "Tam olarak anlatamadim... Belki tamamini duymak istersin.",
        "Bir sey eksik... Sen de hissediyor musun?",
        "O ani tam olarak tarif edemiyorum... Ama hatirliyorum.",
    ]

    CLIFFHANGER_TEMPLATES = [
        "Ve sonra olan sey... {emotion}",
        "Ama asil onemli olan... {insight}",
        "Kimse bilmedi ama... {secret}",
    ]

    def inject_open_loop(self, base_message: str, intensity: float = 0.7,
                          llm_gateway=None, context: str = "") -> str:
        """
        Mesaja acik dongu ekle.
        llm_gateway verilirse: LLM ile kisisellestirilmis dongu olustur.
        Verilmezse: fallback statik listeden sec.
        """
        if random.random() > intensity:
            return base_message

        if llm_gateway is not None:
            try:
                prompt = (
                    f"Asagidaki mesaja dogal ve samimi bir 'acik dongu' (open loop) cumlesi ekle. "
                    f"Cumle tamamlanmamishik hissi vermeli, merak uyandirmali. "
                    f"Uzun olmamali, tek cumle. Mesaj: '{base_message}'. "
                    f"Hedef icerigi: '{context}'. Sadece eklenti cumlecigini yaz."
                )
                loop = asyncio.get_event_loop().run_until_complete(
                    llm_gateway.query(prompt, temperature=0.9, tier=2)
                ) if asyncio.get_event_loop().is_running() else ""
                if loop.strip():
                    return f"{base_message} {loop.strip()}"
            except Exception as e:
                import logging
                logging.warning(f"LLM query failed in inject_open_loop: {e}. Falling back to static templates.")

        loop = random.choice(self.OPEN_LOOP_PHRASES)
        return f"{base_message} {loop}"

    def create_cliffhanger(self, topic: str, target_emotion: str,
                            llm_gateway=None) -> str:
        """
        Bir sonraki etkilesim icin 'devami gelecek' hissi.
        """
        if llm_gateway is not None:
            try:
                prompt = (
                    f"Konu: '{topic}', Hedef duygu: '{target_emotion}'. "
                    f"Bu konuda bir cliffhanger cumlesi yaz. "
                    f"Cumle tamamlanmamali, merak birakmali ve tek cumle olmali."
                )
                result = asyncio.get_event_loop().run_until_complete(
                    llm_gateway.query(prompt, temperature=0.9, tier=2)
                ) if asyncio.get_event_loop().is_running() else ""
                if result.strip():
                    return result.strip() + " (Ama simdi degil...)"
            except Exception as e:
                import logging
                logging.warning(f"LLM query failed in create_cliffhanger: {e}. Falling back to static templates.")

        template = random.choice(self.CLIFFHANGER_TEMPLATES)
        fillers = {
            '{emotion}': target_emotion,
            '{insight}': 'seninle ilgili fark ettigim sey',
            '{secret}': 'sadece sana soyliyebilecegim'
        }
        result = template
        for key, value in fillers.items():
            result = result.replace(key, value)
        return result + " (Ama simdi degil...)"

