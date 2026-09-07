"""Karanlik uclu: GÖREV 2.1 sonrasi sozluk-suz govde.

KALDIRILDI: statik MARKERS sozlugu + kelime-sayma skorlamasi ("mükemmel"
saymak narsisizm olcumu degildir). analyze() artik trait skoru URETMEZ;
uc trait + exploitability gozlemlenmemis (0.0) doner ve metinlerin
DENETIMSUZ temasal yapisi (theme_analysis) tasinir.

generate_strategy() esik mantigi VERBATIM korunur: acikca verilen
sifir-disi profillere ayni vektorler dondurulur; analyze() ciktisi
(sifirlar) 'unavailable' uretir ve shadow mesaji uretilmez.
Tema->vektor eslemesi YAPILMAZ (keyfi esleme uydurma olur); strateji
vektorlerinin yeni derinlik-motoru skorlarina baglanmasi ayri bir
tasarim kararidir.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from agent_core.services.theme_cluster import cluster_texts


class DarkTriadProfile(BaseModel):
    machiavellianism: float = 0.0
    narcissism: float = 0.0
    psychopathy: float = 0.0
    exploitability: float = 0.0
    theme_analysis: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class DarkTriadAnalyzer:
    """
    NOT: v1 sozluk-skorlamasi GÖREV 2.1 ile kaldirildi. Trait alanlari
    geriye-uyumluluk icin korunur; deger yalnizca acik profillerden
    (test/legacy) gelebilir, metinden turetilemez.
    """

    def analyze(self, profile_data: Dict) -> DarkTriadProfile:
        raw_posts = (profile_data or {}).get("posts") or []
        if isinstance(raw_posts, str):
            raw_posts = [raw_posts]
        posts = [p for p in raw_posts if isinstance(p, str) and p.strip()]
        bio = (profile_data or {}).get("bio") or ""
        texts = ([bio] if isinstance(bio, str) and bio.strip() else []) + posts
        themes = cluster_texts(texts)
        return DarkTriadProfile(theme_analysis=themes)

    def generate_strategy(self, profile: DarkTriadProfile) -> Dict:
        if all(getattr(profile, t, 0.0) == 0.0 for t in ("machiavellianism", "narcissism", "psychopathy")):
            # Hiç gözlemlenebilir işaret yok; strateji ÜRETİLMEZ.
            return {'vector': 'unavailable', 'tactic': 'Gözlemlenebilir karanlık üçlü işareti bulunamadı.'}
        if profile.narcissism > 0.7:
            return {'vector': 'mirroring', 'tactic': 'Özel ve seçilmiş hissettir'}
        elif profile.machiavellianism > 0.6:
            return {'vector': 'alliance', 'tactic': 'Karşılıklı çıkar vurgusu'}
        elif profile.psychopathy > 0.5:
            return {'vector': 'thrill', 'tactic': 'Risk ve heyecan'}
        # Kısmi işaretler var ama eşik geçilmedi: yine de empathy UYDURMA;
        # strateji belirsiz işaretlenir ki aşağı akışta kanıt sayılmasın.
        return {'vector': 'unobserved', 'tactic': 'İşaretler eşiğin altında; strateji türetilmedi.'}
