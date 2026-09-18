"""
Rezonans Hesaplayıcı — Epistemik Onarım (2026-09-18)

Bu modülün eski sürümü, LLM'in ürettiği iki sübjektif sayının (`depth`, `energy`)
cosine benzerliğini alıp tek bir sihirli yüzdeye indirgiyor ve sonucu
"ATOMIK_REZONANS - Derin bağlantı mümkün" / "FREKANS_UYUSMAZLIGI - Sistem kapat,
yeni hedef" gibi sahte kesinlik üreten dramatik etiketlerle sunuyordu. Bu durum
bağımsız adli denetimdeki "Kanıt Sözleşmesi ve Epistemik Dürüstlük" kuralını
ihlal ediyordu: iki model tahmininin çarpımı, insan uyumu hakkında hüküm olarak
satılamaz.

Onarım sözleşmesi:
  1. Dramatik basmakalıp etiket YOKTUR. Çıktı; hangi somut kanıta dayandığını
     açıklayan, gerekçeli bir örtüşme (overlap) raporudur.
  2. Karar disiplini üç durumludur: "confirmed" (destekleyici ölçülmüş kanıt var),
     "contradicted" (çatışan ölçülmüş kanıt var), "inference_gap" (karar üretmeye
     yetecek kanıt yok). Kanıt yokluğu asla uyum ya da uyumsuzluk olarak
     etiketlenmez.
  3. Rezonans; hedefin ve kullanıcının GERÇEK kanıt alanları — tutkular
     (`passions`), sürtünme sınırları (`frictions`) ve bilişsel üslup (`cognitive`)
     — üzerinden deterministik ve yerel olarak karşılaştırılır.
  4. Fail-Closed korunur: kullanıcı/hedef authentic vektörü yoksa
     `ResonanceCalculationError` fırlatılır; metinden, achilles skorundan veya
     varsayılan değerlerden vektör/uyum ASLA türetilmez.
  5. Tamamen deterministiktir: aynı girdi her zaman bayt-byte aynı çıktıyı verir.
     Redis, veritabanı veya yeni kütüphane YOKTUR; yalnızca standart kütüphane.
"""

import logging
import math
import re
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Karar durumu: destekleyici kanıt / çatışan kanıt / karar için kanıt yokluğu.
ResonanceState = Literal["confirmed", "contradicted", "inference_gap"]

# --- Ölçüm sabitleri (davranışı kilitli, dramatik olmayan geometrik eşikler) ---
# Bu eşikler "uyum kehaneti" değildir; yalnızca SAĞLANAN iki vektör arasındaki
# ölçülebilir farkın ne zaman çatışma sinyali sayılacağını tanımlar.
_DEPTH_MISMATCH_THRESHOLD = 0.35   # |Δdepth| bunu aşarsa DERINLIK_UYUSMAZLIĞI
_ENERGY_LOW = 0.3                  # kullanıcı enerjisi bunun altındayken...
_ENERGY_HIGH = 0.8                 # ...hedef bunun üstündeyse ENERJI_UYUSMAZLIĞI
# Cosine benzerliğinin "pozitif hizalanma" sinyali sayılması için geometrik
# asgari. Tek başına karar üretmez; yalnızca karar faktörlerine şeffaf girer.
_VECTOR_ALIGNMENT_FLOOR = 0.5
# Bir metin kümesinin "somut kanıt" sayılması için gereken asgari anlamlı
# terim sayısı. Tek terimli tesadüfi eşleşmeler kanıt sayılmaz.
_MIN_SUBSTANTIVE_TERMS = 3

# Token çıkarımında içerik sayılmayan şema/meta alanları. Bunlar ölçüm ya da
# güven metadata'sıdır; insan kanıtı değildir.
_META_KEYS = frozenset({
    "confidence", "data_confidence", "fallback_reason", "resonance_score",
    "sentiment_polarity", "alignment_score", "achilles_score",
    "resonance_potential", "evidence_quotes_count",
})

# Anlamsız yer tutucu değerler içerik değildir.
_SKIP_VALUE_STRINGS = frozenset({"unknown", "unavailable", "none", "null", "true", "false"})

# Küçük, gömülü Türkçe+İngilizce durak kelime listesi. Harici kaynak yok.
_STOPWORDS = frozenset({
    "ve", "ile", "bir", "için", "gibi", "ama", "fakat", "ancak", "çok", "daha",
    "ben", "sen", "biz", "siz", "bu", "şu", "da", "de", "ki", "mi", "mı",
    "mu", "mü", "ya", "ne", "en", "her", "ise", "hem", "olan", "olarak",
    "kadar", "sonra", "önce", "göre", "diye", "böyle", "üzere", "the", "and",
    "for", "with", "that", "this", "from", "are", "was", "you", "your", "his",
    "her", "its", "not", "but", "all", "can", "had", "has", "have", "will",
    "would", "there", "their", "what", "about", "into", "over", "after",
    "before", "who", "how", "when",
})

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_MIN_TOKEN_LEN = 3


class ResonanceCalculationError(Exception):
    """Fırlatılır: Rezonans hesaplaması matematiksel olarak imkansızsa (örn: boş vektörler)."""
    pass


class EvidenceOverlap(BaseModel):
    """Tek bir kanıt alanının gerekçeli karşılaştırma sonucu.

    `overlap=None` => bu alanda ölçüm yapılamadı (kanıt sağlanmadı). 0.0 ile
    karıştırılmamalıdır: 0.0 ölçülmüş bir sonuçtur, None ise dürüst yokluktur.
    """
    domain: str                                     # örn: "tutkular", "sürtünme sınırları"
    state: ResonanceState
    overlap: Optional[float] = None                 # ölçülebildiğinde [0.0, 1.0]
    shared_evidence: List[str] = Field(default_factory=list)      # ölçülen ortak somut öğeler
    conflicting_evidence: List[str] = Field(default_factory=list) # ölçülen çatışan somut öğeler
    rationale: str = ""                             # bu alanın kararı hangi veriye dayanıyor

    model_config = ConfigDict(extra="forbid")


class ResonanceProfile(BaseModel):
    """Epistemik olarak dürüst rezonans raporu.

    `compatibility_score` yalnızca iki authentic vektörün ölçülen cosine
    benzerliğidir; bu vektörler model tahminidir, gözlemsel ölçüm değildir.
    Nihai karar `state` alanındadır ve `decision_factors` ile gerekçelendirilir.
    """
    state: ResonanceState
    compatibility_score: float                      # ölçülen cosine benzerliği (vektörler gerçekten sağlandıysa)
    data_confidence: bool                           # False => çıktı karar değildir (fail-closed)
    rationale: str                                  # skorun/kararın hangi somut veriye dayandığı
    decision_factors: List[str] = Field(default_factory=list)
    domain_overlaps: List[EvidenceOverlap] = Field(default_factory=list)
    frequency_match: Dict[str, float] = Field(default_factory=dict)  # yalnızca ölçülen değerler
    recommended_approach: str                       # dramatik etiket değil; kanıta bağlı düz cümle
    red_flags: list = Field(default_factory=list)
    evidence_sources: List[str] = Field(default_factory=list)        # karara giren gerçek girdi alanları
    vector_provenance: Dict[str, str] = Field(default_factory=dict)  # vektörlerin köken beyanı

    model_config = ConfigDict(extra="forbid")


class ResonanceCalculator:
    """İki profil arasındaki rezonansı, gerçek kanıt alanlarını karşılaştırarak
    gerekçeli biçimde değerlendirir. Skor değil, kanıt raporu üretir."""

    async def execute(self, input_data: Dict, memory, llm_gateway) -> ResonanceProfile:
        # Rezonans, iki tarafın da gerçekten sağlanmış kanıtı üzerinden kurulur.
        # Bir taraf yoksa "hoş görünen" nötr bir değer uydurulmaz (fail-closed).
        user_vector = input_data.get('user_authentic_vector')
        if not self._has_required_dimensions(user_vector):
            raise ResonanceCalculationError(
                "Kullanıcı authentic vector'u mevcut değil; rezonans hesaplanamaz."
            )

        target_vector = input_data.get('target_authentic_vector')
        if target_vector is not None and not self._has_required_dimensions(target_vector):
            raise ResonanceCalculationError(
                "Hedef authentic vector'u geçersiz; rezonans hesaplanamaz."
            )
        if not target_vector:
            raise ResonanceCalculationError(
                "Hedef authentic vector'u mevcut değil; metin, achilles skoru veya varsayılan değerlerden rezonans türetilemez."
            )

        # --- Adım 1: vektör sinyali (şeffaf, kökeni beyanlı) ---
        similarity = self._cosine_similarity(user_vector, target_vector)
        flags = self._detect_red_flags(user_vector, target_vector)

        # --- Adım 2: gerçek kanıt alanlarının gerekçeli karşılaştırması ---
        user_terms, user_sources = self._user_evidence_terms(input_data)
        user_evidence_ok = len(user_terms) >= _MIN_SUBSTANTIVE_TERMS

        domain_keys = ("passions", "frictions", "cognitive")
        domain_results: List[EvidenceOverlap] = [
            self._evaluate_domain(input_data, "passions", "tutkular", "resonance", user_terms, user_evidence_ok),
            self._evaluate_domain(input_data, "frictions", "sürtünme sınırları", "boundary", user_terms, user_evidence_ok),
            self._evaluate_domain(input_data, "cognitive", "bilişsel üslup", "resonance", user_terms, user_evidence_ok),
        ]
        vector_domain = self._vector_domain(similarity, flags, user_vector, target_vector)

        # --- Adım 3: kanıtın dürüst toplanması ---
        state, data_confidence = self._aggregate_state(flags, domain_results)

        decision_factors = self._decision_factors(
            similarity, flags, domain_results, vector_domain, user_vector, target_vector
        )
        rationale = self._rationale(state, decision_factors)
        approach = self._recommended_approach(state, domain_results)

        evidence_sources = ["user_authentic_vector", "target_authentic_vector"]
        evidence_sources.extend(user_sources)
        evidence_sources.extend(
            key for key, d in zip(domain_keys, domain_results)
            if d.state != "inference_gap" or d.overlap is not None
        )

        frequency_match: Dict[str, float] = {"vector_cosine": round(similarity, 3)}
        for key, d in zip(domain_keys, domain_results):
            if d.overlap is not None:
                frequency_match[f"{key}_overlap"] = round(d.overlap, 3)

        return ResonanceProfile(
            state=state,
            compatibility_score=similarity,
            data_confidence=data_confidence,
            rationale=rationale,
            decision_factors=decision_factors,
            domain_overlaps=[vector_domain, *domain_results],
            frequency_match=frequency_match,
            recommended_approach=approach,
            red_flags=flags,
            evidence_sources=evidence_sources,
            vector_provenance=self._vector_provenance(user_vector, target_vector),
        )

    # ------------------------------------------------------------------ #
    # Vektör sinyali — davranışı kilitli ölçüm yordamları
    # ------------------------------------------------------------------ #

    @staticmethod
    def _has_required_dimensions(vector: object) -> bool:
        if not isinstance(vector, dict):
            return False
        return all(
            isinstance(vector.get(dimension), (int, float))
            for dimension in ("depth", "energy")
        )

    def _detailed_match(self, vec1: Dict, vec2: Dict) -> Dict[str, float]:
        return {'overall_match': self._cosine_similarity(vec1, vec2)}

    def _cosine_similarity(self, vec1: Dict, vec2: Dict) -> float:
        numeric_keys = {
            k for k in set(vec1.keys()) & set(vec2.keys())
            if isinstance(vec1[k], (int, float)) and isinstance(vec2.get(k), (int, float))
        }
        if not numeric_keys:
            return 0.0

        dot_product = sum(float(vec1[k]) * float(vec2[k]) for k in numeric_keys)
        magnitude1 = math.sqrt(sum(float(vec1[k])**2 for k in numeric_keys))
        magnitude2 = math.sqrt(sum(float(vec2[k])**2 for k in numeric_keys))

        if magnitude1 == 0 or magnitude2 == 0:
            logger.warning("Resonance calculation failed: Zero magnitude vector encountered.")
            raise ResonanceCalculationError("Vektörlerden birinin magnitude'u SIFIR. Hesaplama yapılamaz.")

        return float(dot_product / (magnitude1 * magnitude2))

    def _detect_red_flags(self, user: Dict, target: Dict) -> list:
        """[033] fix: eski 'surface_focus' koşulu hiçbir üretici tarafından
        doldurulmadığı için DERINLIK_UYUSMAZLIGI bayrağı üretilemezdi (ölü dal).
        Gerçek vektör boyutlarından türetilir."""
        flags = []

        def _num(vec: Dict, key: str):
            v = vec.get(key)
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        u_depth, t_depth = _num(user, "depth"), _num(target, "depth")
        if u_depth is not None and t_depth is not None and abs(u_depth - t_depth) > _DEPTH_MISMATCH_THRESHOLD:
            flags.append("DERINLIK_UYUSMAZLIĞI")

        u_energy, t_energy = _num(user, "energy"), _num(target, "energy")
        if u_energy is not None and t_energy is not None and u_energy < _ENERGY_LOW and t_energy > _ENERGY_HIGH:
            flags.append("ENERJI_UYUSMAZLIĞI")

        return flags

    # ------------------------------------------------------------------ #
    # Kanıt çıkarımı — deterministik, yerel, harici bağımlılıksız
    # ------------------------------------------------------------------ #

    @staticmethod
    def _numeric_dim(vec: Dict, key: str):
        value = vec.get(key)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    def _user_evidence_terms(self, input_data: Dict) -> Tuple[Set[str], List[str]]:
        """Kullanıcı tarafının somut kanıt terimlerini toplar.

        Kaynaklar yalnızca gerçekten katkı sağladıklarında raporlanır; terim
        üretmeyen alan "kullanıldı" diye yazılmaz (sahte dayanak yok).
        """
        terms: Set[str] = set()
        sources: List[str] = []

        profile = input_data.get("user_profile")
        if isinstance(profile, dict):
            before = len(terms)
            self._collect_terms(profile, terms)
            if len(terms) > before:
                sources.append("user_profile")

        mirror = input_data.get("user_mirror")
        if isinstance(mirror, dict):
            before = len(terms)
            self._collect_terms(mirror, terms)
            if len(terms) > before:
                sources.append("user_mirror")

        return terms, sources

    def _collect_terms(self, node: Any, out: Set[str]) -> None:
        """Bilinmeyen şemalardan (dict/list/str iç içe) içerik terimleri çıkarır.

        Şema adları (dict anahtarları) içerik sayılmaz; meta/güven alanları
        atlanır; sayılar ve boolean'lar kanıt değildir.
        """
        if isinstance(node, str):
            for token in _TOKEN_RE.findall(node.lower()):
                if (
                    len(token) >= _MIN_TOKEN_LEN
                    and not token.isdigit()
                    and token not in _STOPWORDS
                    and token not in _SKIP_VALUE_STRINGS
                ):
                    out.add(token)
        elif isinstance(node, dict):
            for key, value in node.items():
                if not isinstance(key, str) or key.startswith("_") or key in _META_KEYS:
                    continue
                self._collect_terms(value, out)
        elif isinstance(node, (list, tuple)):
            for item in node:
                self._collect_terms(item, out)
        # diğer tipler (sayı, bool, None): kanıt değildir, sessizce atlanır

    def _evaluate_domain(
        self,
        input_data: Dict,
        key: str,
        label: str,
        kind: str,
        user_terms: Set[str],
        user_evidence_ok: bool,
    ) -> EvidenceOverlap:
        """Tek kanıt alanını (tutkular / sürtünme sınırları / bilişsel üslup)
        kullanıcı kanıtıyla karşılaştırır. Veri yoksa uydurma ölçüm üretmez."""
        blob = input_data.get(key)
        label_title = label[:1].upper() + label[1:]

        if not blob:
            return EvidenceOverlap(
                domain=label,
                state="inference_gap",
                rationale=f"Hedefin {label} alanı için kanıt sağlanmadı; bu alanda örtüşme ölçülmedi.",
            )

        if isinstance(blob, dict) and blob.get("data_confidence") is False:
            return EvidenceOverlap(
                domain=label,
                state="inference_gap",
                rationale=(
                    f"{label_title} verisi üretici tarafından data_confidence=false olarak işaretlendi "
                    f"(fallback/kanıtsız); örtüşme ölçümüne kanıt olarak girmedi."
                ),
            )

        target_terms: Set[str] = set()
        self._collect_terms(blob, target_terms)
        if len(target_terms) < _MIN_SUBSTANTIVE_TERMS:
            return EvidenceOverlap(
                domain=label,
                state="inference_gap",
                rationale=f"{label_title} alanında ölçülebilir somut içerik yetersiz ({len(target_terms)} anlamlı terim).",
            )

        if not user_evidence_ok:
            return EvidenceOverlap(
                domain=label,
                state="inference_gap",
                rationale="Kullanıcı tarafında karşılaştırılabilir somut kanıt yetersiz; alan değerlendirilemedi.",
            )

        matches = sorted(user_terms & target_terms)

        if kind == "boundary":
            # Sürtünme sınırlarında eşleşme = çatışma sinyali (kullanıcının bir
            # özelliği hedefin beyan edilmiş sınırına çarpıyor).
            overlap = len(matches) / len(target_terms)
            if matches:
                return EvidenceOverlap(
                    domain=label,
                    state="contradicted",
                    overlap=overlap,
                    conflicting_evidence=matches,
                    rationale=(
                        f"Kullanıcı kanıtındaki şu somut öğeler hedefin {label} ile çakışıyor: "
                        f"{', '.join(matches)}."
                    ),
                )
            return EvidenceOverlap(
                domain=label,
                state="confirmed",
                overlap=0.0,
                rationale=(
                    f"Sağlanan kanıtta kullanıcı öğesi hedefin {label} ile çakışmıyor "
                    f"(ölçüm {len(target_terms)} somut sınır terimi üzerinden yapıldı)."
                ),
            )

        # kind == "resonance": eşleşme = paylaşılan somut ilgi/üslup kanıtı.
        if matches:
            overlap = len(matches) / min(len(user_terms), len(target_terms))
            return EvidenceOverlap(
                domain=label,
                state="confirmed",
                overlap=overlap,
                shared_evidence=matches,
                rationale=(
                    f"{label_title} alanında iki tarafı bağlayan ölçülmüş ortak kanıt: {', '.join(matches)}."
                ),
            )
        return EvidenceOverlap(
            domain=label,
            state="inference_gap",
            overlap=0.0,
            rationale=(
                f"{label_title} alanında örtüşen somut kanıt ölçülmedi. Bu bir çelişki kanıtı "
                f"değildir; destekleyici kanıtın yokluğudur."
            ),
        )

    def _vector_domain(
        self, similarity: float, flags: list, user_vector: Dict, target_vector: Dict
    ) -> EvidenceOverlap:
        """Authentic vektörlerin ölçümünü köken beyanıyla raporlar."""
        provenance = self._vector_provenance(user_vector, target_vector)
        disclosure = (
            f"Cosine benzerliği {similarity:.3f}; kullanıcı vektörü kökeni '{provenance['user']}', "
            f"hedef vektörü kökeni '{provenance['target']}'. Bu değerler gözlemsel ölçüm değildir."
        )
        if flags:
            return EvidenceOverlap(
                domain="authentic vektörleri",
                state="contradicted",
                overlap=round(similarity, 3),
                conflicting_evidence=sorted(flags),
                rationale=f"{disclosure} Ölçülen boyut farkları kırmızı bayrak üretti: {', '.join(sorted(flags))}.",
            )
        if similarity >= _VECTOR_ALIGNMENT_FLOOR:
            return EvidenceOverlap(
                domain="authentic vektörleri",
                state="confirmed",
                overlap=round(similarity, 3),
                rationale=f"{disclosure} Pozitif geometrik hizalanma var; ancak tek başına uyum kararı için yeterli kanıt değildir.",
            )
        return EvidenceOverlap(
            domain="authentic vektörleri",
            state="inference_gap",
            overlap=round(similarity, 3),
            rationale=f"{disclosure} Vektör sinyali zayıf; tek başına ne uyum ne uyumsuzluk kanıtı sayılmaz.",
        )

    # ------------------------------------------------------------------ #
    # Dürüst toplama, gerekçe ve yaklaşım cümlesi
    # ------------------------------------------------------------------ #

    @staticmethod
    def _aggregate_state(
        flags: list,
        domain_results: List[EvidenceOverlap],
    ) -> Tuple[ResonanceState, bool]:
        """Karar yalnızca ölçülmüş kanıttan çıkar; kanıt yoksa hüküm de yoktur."""
        conflicts: List[str] = list(flags)
        supports: List[str] = []
        for d in domain_results:
            if d.state == "contradicted":
                conflicts.extend(d.conflicting_evidence)
            elif d.state == "confirmed" and d.shared_evidence:
                supports.extend(d.shared_evidence)

        if conflicts:
            # Çatışma kanıtı destekleyici kanıttan baskın sayılır (fail-safe);
            # her iki liste de karar faktörlerinde açıkça görünür.
            return "contradicted", True
        if supports:
            return "confirmed", True
        # Ne destek ne çatışma ölçülebildi: dürüst cevap "bilmiyoruz"dur.
        return "inference_gap", False

    def _decision_factors(
        self,
        similarity: float,
        flags: list,
        domain_results: List[EvidenceOverlap],
        vector_domain: EvidenceOverlap,
        user_vector: Dict,
        target_vector: Dict,
    ) -> List[str]:
        factors: List[str] = [
            f"Ölçülen vektör benzerliği (cosine): {similarity:.3f} — model tahmini vektörlerden türetilmiştir, gözlemsel ölçüm değildir."
        ]

        u_depth, t_depth = self._numeric_dim(user_vector, "depth"), self._numeric_dim(target_vector, "depth")
        u_energy, t_energy = self._numeric_dim(user_vector, "energy"), self._numeric_dim(target_vector, "energy")
        if "DERINLIK_UYUSMAZLIĞI" in flags and u_depth is not None and t_depth is not None:
            factors.append(
                f"Kırmızı bayrak: DERINLIK_UYUSMAZLIĞI — kullanıcı depth={u_depth}, hedef depth={t_depth} "
                f"(ölçülen fark {abs(u_depth - t_depth):.2f} > {_DEPTH_MISMATCH_THRESHOLD})."
            )
        if "ENERJI_UYUSMAZLIĞI" in flags and u_energy is not None and t_energy is not None:
            factors.append(
                f"Kırmızı bayrak: ENERJI_UYUSMAZLIĞI — kullanıcı energy={u_energy} < {_ENERGY_LOW} iken "
                f"hedef energy={t_energy} > {_ENERGY_HIGH}."
            )

        for d in domain_results:
            if d.shared_evidence:
                factors.append(f"Ortak somut kanıt ({d.domain}): {', '.join(d.shared_evidence)}.")
            if d.conflicting_evidence:
                factors.append(f"Çatışan somut kanıt ({d.domain}): {', '.join(d.conflicting_evidence)}.")
            if d.state == "inference_gap":
                factors.append(f"Kanıt boşluğu ({d.domain}): {d.rationale}")

        if vector_domain.state == "confirmed":
            factors.append("Not: pozitif vektör hizalanması tek başına karar üretmedi; nitel kanıt alanlarıyla birlikte okunmalıdır.")

        return factors

    @staticmethod
    def _rationale(state: ResonanceState, decision_factors: List[str]) -> str:
        header = {
            "confirmed": "Karar durumu: confirmed — destekleyici somut kanıt ölçüldü.",
            "contradicted": "Karar durumu: contradicted — çatışan somut kanıt ölçüldü.",
            "inference_gap": "Karar durumu: inference_gap — karar üretmeye yetecek kanıt yok.",
        }[state]
        body = " ".join(decision_factors)
        if state == "inference_gap":
            closing = (
                " Kanıt yokluğu ne uyum ne uyumsuzluk kanıtıdır; compatibility_score bir uyum "
                "vaadi olarak okunmamalıdır."
            )
        else:
            closing = " Sonuç yalnızca yukarıda listelenen sağlanmış verilere dayanır; bunun ötesine genellenemez."
        return f"{header} Gerekçe: {body}{closing}"

    @staticmethod
    def _recommended_approach(state: ResonanceState, domain_results: List[EvidenceOverlap]) -> str:
        if state == "confirmed":
            shared = sorted({item for d in domain_results for item in d.shared_evidence})[:3]
            return (
                f"Sağlanan kanıtlarda ölçülen ortak noktalar ({', '.join(shared)}) üzerinden "
                f"saygılı ve doğal bir diyalog başlangıcı makul görünüyor."
            )
        if state == "contradicted":
            conflicts = sorted({item for d in domain_results for item in d.conflicting_evidence})[:3]
            detail = f" ({', '.join(conflicts)})" if conflicts else ""
            return (
                f"Ölçülen çatışma sinyalleri{detail} nedeniyle ısrarcı bir yaklaşım önerilmez; "
                f"karşı tarafın sınırlarına saygılı mesafe korunmalıdır."
            )
        return (
            "Yaklaşım önerisi üretmek için yeterli kanıt yok; tutkular, sürtünme sınırları ve "
            "bilişsel üslup alanları sağlanmadan karar verilemez."
        )

    @staticmethod
    def _vector_provenance(user_vector: Dict, target_vector: Dict) -> Dict[str, str]:
        return {
            "user": str(user_vector.get("_epistemic", "belirtilmemiş")),
            "target": str(target_vector.get("_epistemic", "belirtilmemiş")),
        }
