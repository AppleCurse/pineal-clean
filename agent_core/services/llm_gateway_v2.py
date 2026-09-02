"""
Pineal llm_gateway_v2.py - Capability-based routing fabric
- Dynamic Nous free pool discovery
- Hard constraints + scoring
- PAID_ESCALATION_LOCK, CAPABILITY_LOCK, PROVIDER_DEFAULT_LOCK, UNKNOWN_MODEL_LOCK, ACTUAL_MODEL_AUDIT
- QuotaState multi-dimensional (RPM/RPD/TPM/TPD)
- No provider default

---
Denetçi notu (2026-09-02, ekleyen: Arena agent):
Bu dosya kullanıcının "routing fabric" tasarımının BİRİNCİ SÜRÜM taslağıdır.
Production'a BAĞLI DEĞİLDİR: mevcut canlı yol `llm_gateway.py` (v1) + UnifiedRouter
üzerinden çalışmaya devam eder; bu modülü hiçbir production call-site import etmez.
Merge öncesi yapılacaklar: gerçek provider smoke koşusu (kullanıcının kendi
anahtarlarıyla), fiyat tablosunun spend-guard'a bağlanması, epistemik sözleşme
(OBSERVED/INTERPRETED) tiplemesinin taşınması.

İskelete yapılan kasıtlı düzeltmeler (kullanıcı tasarımının kendi kurallarına
sadık kalmak için):
1. Dört "known_free" slug (stepfun/step-3.7-flash:free, upstage/solar-pro4:free,
   meituan/longcat-2.0:free, poolside/laguna:free) hardcode EDİLMEDİ. Tasarımın
   kendi kuralı bunu yasaklıyor: DISCOVERED -> VALIDATED -> FREE-VALIDATED ->
   CAPABILITY-VALIDATED -> ELIGIBLE. Bu slug'lar `SEED_ROUTES` içinde
   "kullanıcı panel bildirimi; hesap endpoint'inin doğrulamasını bekliyor"
   statüsünde durur; hiçbiri statik olarak ELIGIBLE sayılmaz.
2. Nous ücretli fiyatları (Luna $0.20/$1.20, Sonnet 5 $1.60/$8) kaynak olarak
   "kullanıcının kendi hesabı" yazılarak ACCOUNT_VERIFIED işaretlendi. Bu oturumda
   bağımsız web teyidi yapılamadı; hesap sahibinin paneli birinci elden kanıttır.
3. İskelenin scoring fonksiyonundaki ölçüm hatası düzeltildi: RPM kalanı latency
   değildir; latency artık OBSERVED gecikme ölçümünden normalleştirilir, ölçüm
   yoksa nötr 0.5 alınır (uydurma avantaj üretilmez).
4. Hata sınıflandırma string-match ("429" in str(e)) yerine tiplidir
   (ProviderError.status_code).
5. `verified=True` keşif anında basılmıyordu — iskelede hem UNKNOWN_MODEL_LOCK
   "verified olmayan elenir" diyor hem discovery verified=True basıyordu (kendi
   pipeline'ını bypass). Burada discovery validated_stage=DISCOVERED üretir;
   terfi yalnız `promote_validated()` ile olur.
- Fiyat/kota değerleri kaynak-etiketlidir: DOCUMENTED / ACCOUNT_VERIFIED /
  OBSERVED / ESTIMATED — etiketsiz sayı yazılmaz.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Tipler                                                                       #
# --------------------------------------------------------------------------- #

class Capability(Enum):
    VISION = "vision"
    VISION_VIDEO = "vision_video"
    STRONG_REASONING = "strong_reasoning"
    FAST_CHEAP = "fast_cheap"
    TOOL_USE = "tool_use"
    LONG_CONTEXT = "long_context"


class CostClass(Enum):
    FREE = "free"
    PAID = "paid"


class QuotaConfidence(Enum):
    DOCUMENTED = "documented"
    ACCOUNT_VERIFIED = "account_verified"
    OBSERVED = "observed"
    ESTIMATED = "estimated"


class ValidationStage(Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"               # endpoint varlığı + pricing alanı okundu
    FREE_VALIDATED = "free_validated"     # prompt==0 AND completion==0 açıkça kanıtlı
    CAPABILITY_VALIDATED = "capability_validated"  # yetenek iddiası kanıtlandı
    ELIGIBLE = "eligible"


# --------------------------------------------------------------------------- #
# Kilit istisnaları                                                            #
# --------------------------------------------------------------------------- #

class PaidEscalationBlocked(Exception):
    """FREE havuz tükendi ama paid_allowed/budget yok — sessiz ücretli geçiş yasak."""


class ProviderDefaultBlocked(Exception):
    """Model açıkça seçilmeden provider'a istek atılamaz (silent default yasak)."""


class UnknownPriceBlocked(Exception):
    """PAID çağrı için fiyat bilinmiyor — BLOCK (UNKNOWN_PRICE_LOCK)."""


class CatalogUnavailable(Exception):
    """Provider /models katalogu okunamadı — discovery fail-closed durur."""


class ProviderError(Exception):
    """Taşıma sağlayıcı hatası; status_code tiplidir (429/5xx/4xx ayrımı)."""

    def __init__(self, provider: str, status_code: int, message: str = "") -> None:
        super().__init__(f"[{provider}] HTTP {status_code}: {message}")
        self.provider = provider
        self.status_code = status_code


# --------------------------------------------------------------------------- #
# Durum modelleri                                                             #
# --------------------------------------------------------------------------- #

@dataclass
class QuotaState:
    """Çok boyutlu kota. Tek RPM sayacı YETERLİ DEĞİL (Groq/Google docs)."""

    rpm_remaining: Optional[int] = None
    rpd_remaining: Optional[int] = None
    tpm_remaining: Optional[int] = None
    tpd_remaining: Optional[int] = None
    concurrency_remaining: Optional[int] = None
    reset_at: float = 0.0
    confidence: QuotaConfidence = QuotaConfidence.ESTIMATED
    source: str = "unprobed"

    def exhausted(self) -> bool:
        """Bilinen herhangi bir boyut bitmişse koruyucu şekilde 'tükendi' say."""
        for v in (self.rpm_remaining, self.rpd_remaining):
            if v is not None and v <= 0:
                return True
        return False

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Provider response header'larından GERÇEK kalanı oku (OBSERVED terfisi)."""
        mapping = {
            "x-ratelimit-remaining-requests": "rpm_remaining",
            "x-ratelimit-remaining-tokens": "tpm_remaining",
            "ratelimit-remaining-requests": "rpm_remaining",
            "ratelimit-remaining-tokens": "tpm_remaining",
        }
        lowered = {k.lower(): v for k, v in headers.items()}
        hit = False
        for hdr, attr in mapping.items():
            raw = lowered.get(hdr)
            if raw is None:
                continue
            try:
                setattr(self, attr, int(float(raw)))
                hit = True
            except ValueError:
                continue
        if hit and self.confidence is QuotaConfidence.ESTIMATED:
            self.confidence = QuotaConfidence.OBSERVED
            self.source = "provider_headers"


@dataclass
class ModelCandidate:
    id: str
    provider: str
    base_url: str
    capabilities: List[Capability]
    context_length: int
    cost_class: CostClass
    cost_per_1m_in: Optional[float]     # None = bilinmiyor (UNKNOWN_PRICE_LOCK devrede)
    cost_per_1m_out: Optional[float]
    quota: QuotaState = field(default_factory=QuotaState)
    verified: bool = False              # UNKNOWN_MODEL_LOCK: False ise production'a giremez
    free_verified: bool = False         # pricing==0 açıkça kanıtlandı mı
    validation_stage: ValidationStage = ValidationStage.DISCOVERED
    observed_latency_ms: Optional[float] = None   # OBSERVED gecikme; None ise skor nötr
    price_source: str = ""              # fiyatın nereden geldiği (hesap paneli / docs / katalog)
    api_key_env: str = ""               # credential'ı hangi env okur

    def price_known(self) -> bool:
        return self.cost_per_1m_in is not None and self.cost_per_1m_out is not None


@dataclass
class TaskSpec:
    name: str
    required_caps: Sequence[Capability] = ()
    min_context: int = 0
    cost_class: CostClass = CostClass.FREE
    paid_allowed: bool = False          # görev paid'e çıkabilir mi (policy kararı)
    budget_remaining: Optional[float] = None   # USD; None = bilinmiyor (paid seçimini bloke eder)
    estimated_cost: float = 0.0
    requested_model_explicit: bool = True
    quality_scores: Dict[str, float] = field(default_factory=dict)  # aday kalite skoru 0..1 (bench varsa)


# --------------------------------------------------------------------------- #
# KİLİTLER — hard constraints (skorlamadan önce, asla ihlal edilemez)         #
# --------------------------------------------------------------------------- #

def provider_default_lock(task: TaskSpec) -> None:
    """PROVIDER_DEFAULT_LOCK — provider default'a asla düşme (Nous sessiz-paid bug'ı)."""
    if not task.requested_model_explicit:
        raise ProviderDefaultBlocked(
            "Model açıkça seçilmedi; provider default davranışına güvenilmez."
        )


def passes_hard_constraints(task: TaskSpec, c: ModelCandidate) -> Tuple[bool, str]:
    # CAPABILITY_LOCK — vision isteyen göreve text-only model: IMPOSSIBLE
    if Capability.VISION in task.required_caps and Capability.VISION not in c.capabilities:
        return False, "capability_lock:vision"
    if Capability.VISION_VIDEO in task.required_caps and Capability.VISION_VIDEO not in c.capabilities:
        return False, "capability_lock:vision_video"
    if task.min_context and c.context_length < task.min_context:
        return False, "min_context"
    # UNKNOWN_MODEL_LOCK — doğrulanmamış aday production routing'e giremez
    if not c.verified:
        return False, "unknown_model_lock"
    # FREE görev PAID adayı — PAID_ESCALATION_LOCK (hard)
    if task.cost_class is CostClass.FREE and c.cost_class is CostClass.PAID:
        return False, "paid_escalation_lock"
    # FREE iddiası kanıtsızsa (free_verified=False) FREE havuza giremez
    if task.cost_class is CostClass.FREE and not c.free_verified:
        return False, "free_unverified"
    # UNKNOWN_PRICE_LOCK — PAID çağrı fiyat bilinmeden BLOCK
    if c.cost_class is CostClass.PAID and not c.price_known():
        return False, "unknown_price_lock"
    return True, "ok"


# --------------------------------------------------------------------------- #
# SKORLAMA — hard constraints'i geçenler arasında                              #
# --------------------------------------------------------------------------- #

SCORING_WEIGHTS = {
    "quality": 0.30,
    "latency": 0.20,
    "quota": 0.20,
    "cost": 0.15,
    "reliability": 0.10,
    "capability": 0.05,
}

_RELIABILITY_BY_CONFIDENCE = {
    QuotaConfidence.DOCUMENTED: 0.7,
    QuotaConfidence.ACCOUNT_VERIFIED: 0.9,
    QuotaConfidence.OBSERVED: 1.0,
    QuotaConfidence.ESTIMATED: 0.4,
}


def _latency_score(c: ModelCandidate) -> float:
    """OBSERVED gecikmeden türet; ölçüm yoksa NÖTR 0.5 (uydurma avantaj yok)."""
    if c.observed_latency_ms is None:
        return 0.5
    # 0ms -> 1.0 ; 8000ms+ -> ~0.0 (yumuşak doyma)
    return max(0.0, 1.0 - min(c.observed_latency_ms, 8000.0) / 8000.0)


def _quota_score(c: ModelCandidate) -> float:
    if c.quota.rpd_remaining is None:
        return 0.5  # kota bilinmiyor -> nötr (ceza değil, avantaj değil)
    return min(max(c.quota.rpd_remaining, 0) / 14400.0, 1.0)


def _cost_score(c: ModelCandidate, task: TaskSpec) -> float:
    if c.cost_class is CostClass.FREE:
        return 1.0
    if not c.price_known():
        return 0.0
    # task.estimated_cost token varsayımı üzerinden ucuzluk; 0 ücret imkânsız PAID'de
    in_p, out_p = c.cost_per_1m_in or 0.0, c.cost_per_1m_out or 0.0
    blended = (in_p + out_p) / 2.0
    return max(0.0, 1.0 - min(blended / 10.0, 1.0))


def score_candidate(task: TaskSpec, c: ModelCandidate) -> float:
    quality = task.quality_scores.get(c.id, 0.5)
    return (
        quality * SCORING_WEIGHTS["quality"]
        + _latency_score(c) * SCORING_WEIGHTS["latency"]
        + _quota_score(c) * SCORING_WEIGHTS["quota"]
        + _cost_score(c, task) * SCORING_WEIGHTS["cost"]
        + _RELIABILITY_BY_CONFIDENCE[c.quota.confidence] * SCORING_WEIGHTS["reliability"]
        + min(len(set(c.capabilities) - set(task.required_caps)), 4) / 4.0 * SCORING_WEIGHTS["capability"]
    )


# --------------------------------------------------------------------------- #
# CIRCUIT BREAKER — 429 / 5xx / 4xx sınıflandırmalı                           #
# --------------------------------------------------------------------------- #

@dataclass
class CircuitState:
    cooldown_until: float = 0.0
    quarantined: bool = False
    quarantine_reason: str = ""
    consecutive_5xx: int = 0


class CircuitBreaker:
    def __init__(self, cooldown_429: float = 60.0, cooldown_5xx_after: int = 2) -> None:
        self._states: Dict[str, CircuitState] = {}
        self.cooldown_429 = cooldown_429
        self.cooldown_5xx_after = cooldown_5xx_after

    def _state(self, provider: str) -> CircuitState:
        return self._states.setdefault(provider, CircuitState())

    def is_open(self, provider: str) -> bool:
        st = self._state(provider)
        if st.quarantined:
            return True
        return time.time() < st.cooldown_until

    def record_success(self, provider: str) -> None:
        st = self._state(provider)
        st.consecutive_5xx = 0
        st.cooldown_until = 0.0

    def record_error(self, err: ProviderError) -> None:
        st = self._state(err.provider)
        if err.status_code == 429:
            st.cooldown_until = time.time() + self.cooldown_429          # cooldown
        elif 500 <= err.status_code < 600:
            st.consecutive_5xx += 1
            if st.consecutive_5xx >= self.cooldown_5xx_after:
                st.cooldown_until = time.time() + self.cooldown_429      # retry sonrası cooldown
        elif 400 <= err.status_code < 500:
            st.quarantined = True                                        # quarantine (auth/geo/config)
            st.quarantine_reason = f"HTTP {err.status_code}"

    def reset_quarantine(self, provider: str) -> None:
        self._states[provider] = CircuitState()


# --------------------------------------------------------------------------- #
# DYNAMIC FREE-POOL DISCOVERY — Nous (ve herhangi OpenAI-uyumlu katalog)      #
# --------------------------------------------------------------------------- #

# Kullanıcının kendi Nous panelinden bildirdiği rotalar. Bunlar burada
# "bilinen gerçek" DEĞİL; hesap endpoint'inin doğrulamasını bekleyen TOHUM'lardır.
# Doğrulama: discover_free_pool() canlı /models + pricing==0 ile kanıtlar.
SEED_ROUTES: Tuple[str, ...] = (
    "stepfun/step-3.7-flash:free",
    "upstage/solar-pro4:free",
    "meituan/longcat-2.0:free",
    "poolside/laguna:free",
)


def _parse_price_zero(pricing: Any) -> Optional[bool]:
    """pricing alanından 'açıkça ücretsiz' kanıtı çıkar. Alan yok/okunamıyorsa
    None döner -> UNKNOWN_PRICE_LOCK adayı free saymaz (fail-closed)."""
    if not isinstance(pricing, dict):
        return None
    try:
        p_in = float(pricing.get("prompt"))
        p_out = float(pricing.get("completion"))
    except (TypeError, ValueError):
        return None
    return p_in == 0.0 and p_out == 0.0


def catalog_row_to_candidate(
    row: Dict[str, Any],
    *,
    provider: str,
    base_url: str,
    api_key_env: str,
) -> Optional[ModelCandidate]:
    """Tek bir /models satırını DISCOVERED adaya çevirir (network-free, test edilebilir).

    free_verified YALNIZCA pricing==0 açıkça kanıtlıysa True olur; yoksa False.
    `verified` burada False kalır — gerçek terfi validate_candidate() ister.
    """
    model_id = row.get("id")
    if not isinstance(model_id, str) or not model_id:
        return None
    free_proof = _parse_price_zero(row.get("pricing"))
    caps: List[Capability] = [Capability.FAST_CHEAP]
    arch = row.get("architecture") or {}
    modality = str(arch.get("modality") or row.get("modality") or "")
    if "image" in modality:
        caps.append(Capability.VISION)
    if "video" in modality:
        caps.append(Capability.VISION_VIDEO)
    ctx = row.get("context_length") or row.get("top_provider", {}).get("context_length") or 0
    try:
        ctx = int(ctx)
    except (TypeError, ValueError):
        ctx = 0
    if ctx >= 500_000:
        caps.append(Capability.LONG_CONTEXT)
    stage = ValidationStage.FREE_VALIDATED if free_proof is True else ValidationStage.DISCOVERED
    return ModelCandidate(
        id=model_id,
        provider=provider,
        base_url=base_url,
        capabilities=caps,
        context_length=ctx,
        cost_class=CostClass.FREE if free_proof is True else CostClass.PAID,
        cost_per_1m_in=0.0 if free_proof is True else None,
        cost_per_1m_out=0.0 if free_proof is True else None,
        quota=QuotaState(confidence=QuotaConfidence.ESTIMATED, source="catalog"),
        verified=False,                    # UNKNOWN_MODEL_LOCK: terfi validate_candidate ister
        free_verified=(free_proof is True),
        validation_stage=stage,
        price_source=f"{provider} catalog pricing field" if free_proof is not None else "",
        api_key_env=api_key_env,
    )


def validate_candidate(c: ModelCandidate) -> ModelCandidate:
    """DISCOVERED -> (FREE_VALIDATED ise) CAPABILITY_VALIDATED -> ELIGIBLE terfisi.

    Yetenek kanıtı katalog modality alanından geliyorsa capability zaten
    FREE_VALIDATED aşamada okundu; burada yalnız varlık + tutarlılık mühürlenir.
    Gerçek dünyada buraya tek-token smoke çağrısı eklenmelidir (kullanıcı
    anahtarıyla, bu sandbox'ta değil).
    """
    if c.validation_stage in (ValidationStage.FREE_VALIDATED, ValidationStage.VALIDATED):
        c.validation_stage = ValidationStage.CAPABILITY_VALIDATED
    if c.validation_stage is ValidationStage.CAPABILITY_VALIDATED:
        c.verified = True
        c.validation_stage = ValidationStage.ELIGIBLE
    return c


async def discover_free_pool(
    *,
    provider: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    http_get: Optional[Callable[[str, Dict[str, str]], Awaitable[Tuple[int, Dict[str, Any]]]]] = None,
) -> List[ModelCandidate]:
    """GET {base_url}/models -> pricing==0 free rotaları DISCOVERED olarak üret.

    Fail-closed: katalog okunamazsa CatalogUnavailable fırlatır; asla "muhtemelen
    şunlar vardır" listesi ÜRETMEZ. `http_get` testlerde enjekte edilir; verilmezse
    httpx kullanılır (httpx yoksa CatalogUnavailable).
    """

    url = (base_url or os.getenv("NOUS_API_BASE") or "https://inference-api.nousresearch.com/v1").rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    if http_get is None:
        try:
            import httpx
        except ImportError as exc:
            raise CatalogUnavailable("httpx yok; discovery çalışamaz") from exc

        async def _httpx_get(u: str, h: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(u, headers=h)
                return resp.status_code, resp.json()

        http_get = _httpx_get

    status, payload = await http_get(url, headers)
    if status != 200:
        raise CatalogUnavailable(f"{provider} katalog HTTP {status}")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise CatalogUnavailable(f"{provider} katalog beklenmedik şema: {str(payload)[:120]!r}")

    out: List[ModelCandidate] = []
    for row in rows:
        cand = catalog_row_to_candidate(row, provider=provider, base_url=base_url or url.rsplit("/models", 1)[0], api_key_env="NOUS_API_KEY")
        if cand is None or cand.cost_class is not CostClass.FREE:
            continue  # yalnız free rotalar havuza girer; paid ayrı policy konusu
        out.append(cand)
    return out


# --------------------------------------------------------------------------- #
# AUDIT                                                                        #
# --------------------------------------------------------------------------- #

@dataclass
class AuditRecord:
    requested_model: str
    provider: str
    actual_model: str
    cost_class: str
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    latency_ms: Optional[float]
    fallback_reason: str = ""


@dataclass
class RouteResult:
    response: Any
    audit: AuditRecord
    candidate: ModelCandidate


# --------------------------------------------------------------------------- #
# ROUTER — engine (taşıma enjekte edilir; bu sayede test edilebilir)          #
# --------------------------------------------------------------------------- #

TransportFn = Callable[[ModelCandidate, TaskSpec], Awaitable[Tuple[Any, Dict[str, str]]]]


class RoutingFabric:
    """Free-pool önce; paid yalnız AÇIK policy kararıyla.

    Üç şartın üçü de olmadan PAID çağrı yapılamaz:
      1) task.paid_allowed, 2) free havuz tükendi, 3) bütçe > tahmini maliyet.
    """

    def __init__(self, candidates: Sequence[ModelCandidate], breaker: Optional[CircuitBreaker] = None) -> None:
        self.candidates: List[ModelCandidate] = list(candidates)
        self.breaker = breaker or CircuitBreaker()
        self.audit_log: List[AuditRecord] = []

    # -- çekirdek ------------------------------------------------------------ #

    def eligible(self, task: TaskSpec) -> List[ModelCandidate]:
        pool = [
            c for c in self.candidates
            if passes_hard_constraints(task, c)[0]
            and not c.quota.exhausted()
            and not self.breaker.is_open(c.provider)
        ]
        pool.sort(key=lambda c: score_candidate(task, c), reverse=True)
        return pool

    async def route(self, task: TaskSpec, transport: TransportFn) -> RouteResult:
        provider_default_lock(task)

        for cand in self.eligible(task):
            try:
                response, headers = await transport(cand, task)
            except ProviderError as err:
                self.breaker.record_error(err)
                cand.quota.rpm_remaining = 0 if err.status_code == 429 else cand.quota.rpm_remaining
                continue
            self.breaker.record_success(cand.provider)
            cand.quota.update_from_headers(headers)
            usage = _extract_usage(response)
            audit = AuditRecord(
                requested_model=cand.id,
                provider=cand.provider,
                actual_model=_extract_actual_model(response, headers, cand.id),
                cost_class=cand.cost_class.value,
                tokens_in=usage.get("in"),
                tokens_out=usage.get("out"),
                latency_ms=usage.get("latency_ms"),
            )
            cand.observed_latency_ms = audit.latency_ms or cand.observed_latency_ms
            self.audit_log.append(audit)
            return RouteResult(response=response, audit=audit, candidate=cand)

        # FREE havuz tükendi -> ESCALATION CHECK (fallback DEĞİL, state machine)
        if task.cost_class is CostClass.FREE:
            if not task.paid_allowed:
                raise PaidEscalationBlocked("Free havuz tükendi; görev paid'e kapalı (degraded dönülmeli).")
            return await self._escalate_to_paid(task, transport)
        raise PaidEscalationBlocked("Uygun PAID aday kalmadı veya hepsinin devresi açık.")

    async def _escalate_to_paid(self, task: TaskSpec, transport: TransportFn) -> RouteResult:
        paid_variants = [
            c for c in self.candidates
            if c.cost_class is CostClass.PAID and c.verified
        ]
        for c in paid_variants:
            if not c.price_known():
                raise UnknownPriceBlocked(f"{c.id}: PAID ama fiyat kaydı yok (UNKNOWN_PRICE_LOCK).")
        # PAID_ESCALATION_LOCK son şart: bütçe
        cheapest = min(paid_variants, key=lambda c: (c.cost_per_1m_in or 0) + (c.cost_per_1m_out or 0)) if paid_variants else None
        if cheapest is None:
            raise PaidEscalationBlocked("Free tükendi; doğrulanmış PAID aday yok.")
        if task.budget_remaining is None or task.budget_remaining <= max(task.estimated_cost, 0.0):
            raise PaidEscalationBlocked("Bütçe yetersiz/bilinmiyor; paid escalation BLOCK.")
        paid_task = TaskSpec(
            name=task.name + " (paid-escalation)",
            required_caps=task.required_caps,
            min_context=task.min_context,
            cost_class=CostClass.PAID,
            paid_allowed=True,
            budget_remaining=task.budget_remaining,
            estimated_cost=task.estimated_cost,
            quality_scores=task.quality_scores,
        )
        return await self.route(paid_task, transport)


# --------------------------------------------------------------------------- #
# Yardımcılar                                                                  #
# --------------------------------------------------------------------------- #

def _extract_actual_model(response: Any, headers: Dict[str, str], fallback: str) -> str:
    if isinstance(response, dict):
        model = response.get("model")
        if isinstance(model, str) and model:
            return model
    for key in ("x-actual-model", "x-model-used"):
        val = headers.get(key) or headers.get(key.title())
        if val:
            return val
    return fallback


def _extract_usage(response: Any) -> Dict[str, Any]:
    usage: Dict[str, Any] = {"in": None, "out": None, "latency_ms": None}
    if isinstance(response, dict):
        u = response.get("usage") or {}
        if isinstance(u, dict):
            usage["in"] = u.get("prompt_tokens")
            usage["out"] = u.get("completion_tokens")
        lm = response.get("_latency_ms")
        if isinstance(lm, (int, float)):
            usage["latency_ms"] = float(lm)
    return usage


# --------------------------------------------------------------------------- #
# SEED REGISTRY — kaynak etiketli; hiçbiri zarflanmış gerçek DEĞİL            #
# --------------------------------------------------------------------------- #

def build_seed_registry() -> List[ModelCandidate]:
    """Kullanıcının 2026-09-02 tasarımındaki başlangıç havuzu.

    Kural: etiketli kaynak olmayan sayı yok. `verified=True` yalnızca resmi
    providers docs'unun bu oturumda teyit ettiği adaylarda; Nous paid fiyatları
    kullanıcının kendi hesap panelinden (ACCOUNT_VERIFIED) — katalog smoke'u
    kullanıcı tarafında koşulana kadar bağımsız teyit askıda.
    """
    return [
        # --- Groq free fast-worker (Groq docs deprecations sayfası önerisi) ---
        ModelCandidate(
            id="groq/openai/gpt-oss-120b", provider="groq",
            base_url="https://api.groq.com/openai/v1",
            capabilities=[Capability.FAST_CHEAP, Capability.TOOL_USE],
            context_length=131_072, cost_class=CostClass.FREE,
            cost_per_1m_in=0.0, cost_per_1m_out=0.0,
            quota=QuotaState(rpm_remaining=30, rpd_remaining=14_400,
                             confidence=QuotaConfidence.DOCUMENTED, source="groq free tier docs"),
            verified=True, free_verified=True,
            validation_stage=ValidationStage.ELIGIBLE,
            price_source="groq free tier", api_key_env="GROQ_API_KEY",
        ),
        ModelCandidate(
            id="groq/openai/gpt-oss-20b", provider="groq",
            base_url="https://api.groq.com/openai/v1",
            capabilities=[Capability.FAST_CHEAP, Capability.TOOL_USE],
            context_length=131_072, cost_class=CostClass.FREE,
            cost_per_1m_in=0.0, cost_per_1m_out=0.0,
            quota=QuotaState(rpm_remaining=30, rpd_remaining=14_400,
                             confidence=QuotaConfidence.DOCUMENTED, source="groq free tier docs"),
            verified=True, free_verified=True,
            validation_stage=ValidationStage.ELIGIBLE,
            price_source="groq free tier", api_key_env="GROQ_API_KEY",
        ),
        # --- Nous PAID (kullanıcının hesabı; fiyat panel bildirimi) -----------
        ModelCandidate(
            id="nous/openai/gpt-5.6-luna", provider="nous",
            base_url="https://inference-api.nousresearch.com/v1",
            capabilities=[Capability.STRONG_REASONING, Capability.FAST_CHEAP, Capability.VISION],
            context_length=1_050_000, cost_class=CostClass.PAID,
            cost_per_1m_in=0.20, cost_per_1m_out=1.20,
            quota=QuotaState(confidence=QuotaConfidence.ACCOUNT_VERIFIED,
                             source="user dashboard 2026-09-02"),
            verified=True, free_verified=False,
            validation_stage=ValidationStage.ELIGIBLE,
            price_source="user Nous dashboard (ACCOUNT_VERIFIED); OpenAI listesi 30 Tem 2026'da aynı fiyata indi",
            api_key_env="NOUS_API_KEY",
        ),
        ModelCandidate(
            id="nous/anthropic/claude-sonnet-5", provider="nous",
            base_url="https://inference-api.nousresearch.com/v1",
            capabilities=[Capability.STRONG_REASONING, Capability.VISION, Capability.TOOL_USE, Capability.LONG_CONTEXT],
            context_length=1_000_000, cost_class=CostClass.PAID,
            cost_per_1m_in=1.60, cost_per_1m_out=8.0,
            quota=QuotaState(confidence=QuotaConfidence.ACCOUNT_VERIFIED,
                             source="user dashboard 2026-09-02"),
            verified=True, free_verified=False,
            validation_stage=ValidationStage.ELIGIBLE,
            price_source="user Nous dashboard (ACCOUNT_VERIFIED); Anthropic listesi $2/$10 kalıcı",
            api_key_env="NOUS_API_KEY",
        ),
    ]
