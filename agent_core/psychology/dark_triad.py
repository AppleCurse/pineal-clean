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


# GÖREV 2 artığı: derinlik->strateji eşikleri (tasarım kararı, test-kilitli).
# Öncelik: mirroring > alliance > thrill.
DEPTH_MIRRORING_REACTION = 0.40
DEPTH_ALLIANCE_REPETITION = 0.40


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

    def strategy_from_depth(self, depth: Dict) -> Dict:
        """GÖREV 2 artığı: derinlik-motoru yapısal indekslerinden strateji.

        Eşikler tasarım kararıdır (test-kilitli); öncelik mirroring >
        alliance > thrill. verdict != ok ise 'unavailable'; eşik-altı ok
        ise 'unobserved'. TOTAL: bozuk şekilde çökmez, sinyal anlık
        görüntüsü 'signal' altında denetime açık taşınır.
        """
        nope = {'vector': 'unavailable',
                'tactic': 'Gözlemlenebilir karanlık üçlü işareti bulunamadı.'}
        if not isinstance(depth, dict) or depth.get("verdict") != "ok":
            return dict(nope, source="psychodynamic_depth", signal=None)
        channels = depth.get("channels")
        if not isinstance(channels, dict):
            return dict(nope, source="psychodynamic_depth", signal=None)
        decl = channels.get("declaration")
        rhythm = channels.get("rhythm")
        dsig = decl.get("signals") if isinstance(decl, dict) else None
        rsig = rhythm.get("signals") if isinstance(rhythm, dict) else None
        dsig = dsig if isinstance(dsig, dict) else {}
        rsig = rsig if isinstance(rsig, dict) else {}
        kinds = rsig.get("rupture_kinds")
        kinds = list(kinds) if isinstance(kinds, list) else []
        n_rup = rsig.get("n_ruptures")
        reaction = depth.get("reaction_formation_index")
        repetition = dsig.get("repetition_score")
        signal = {"reaction_formation_index": reaction,
                  "repetition_score": repetition,
                  "n_ruptures": n_rup,
                  "rupture_kinds": kinds}

        def _num(v):
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        reaction_n, repetition_n = _num(reaction), _num(repetition)
        ruptured = (
            (isinstance(n_rup, int) and not isinstance(n_rup, bool) and n_rup >= 1)
            or "entropy_jump" in kinds
        )
        if reaction_n is not None and reaction_n >= DEPTH_MIRRORING_REACTION:
            return {'vector': 'mirroring',
                    'tactic': 'Savunulan benlik idealini ve vitrini aynala',
                    'source': 'psychodynamic_depth', 'signal': signal}
        if repetition_n is not None and repetition_n >= DEPTH_ALLIANCE_REPETITION:
            return {'vector': 'alliance',
                    'tactic': 'Kompülsif tekrar döngüsüne uyumlu öngörülebilir ortak çıkar',
                    'source': 'psychodynamic_depth', 'signal': signal}
        if ruptured:
            return {'vector': 'thrill',
                    'tactic': 'Faz kırılması ve volatiliteye uyumlu risk',
                    'source': 'psychodynamic_depth', 'signal': signal}
        return {'vector': 'unobserved',
                'tactic': 'İşaretler eşiğin altında; strateji türetilmedi.',
                'source': 'psychodynamic_depth', 'signal': signal}
