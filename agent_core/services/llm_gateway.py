import contextvars
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, List, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_core.services.response_cache import build_cache_from_env

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMCallScope:
    """Task-local collector used to bind call records to one agent execution.

    Context variables are copied per asyncio task, so concurrent agents sharing a
    gateway cannot consume each other's records. The records live in the scope as
    well as in the bounded diagnostic ``call_log``; evidence never relies on a
    mutable global log slice.
    """

    task_id: Optional[str]
    agent_id: Optional[str]
    records: List[dict[str, Any]] = field(default_factory=list)

    @property
    def call_ids(self) -> List[str]:
        return [record["call_id"] for record in self.records]


_active_call_scope: contextvars.ContextVar[Optional[LLMCallScope]] = contextvars.ContextVar(
    "llm_call_scope", default=None
)

class SpendCapExceeded(RuntimeError):
    """P2-MALİYET: canlı harcama üst limiti aşıldı — daha fazla çağrı reddedilir."""


class LLMGateway:
    MODEL_REGISTRY = {
        "solar_pro4": "upstage/solar-pro4",
        "ling_3_flash": "inclusionai/ling-3.0-flash",
        "deepseek_v4_flash": "deepseek/deepseek-v4-flash",
        "glm_5_2": "z-ai/glm-5.2",
        "deepseek_v4_pro": "deepseek/deepseek-v4-pro",
        "gemini_3_7_flash": "google/gemini-3.7-flash"
    }

    MODEL_PRICING = {
        # Fiyatlar 2026-08-30'da OpenRouter kataloğundan doğrulandı (promo/listed,
        # cached-effective değil). Kaynak: /api/v1/models + model sayfaları.
        # Not: solar-pro4/ling-3.0-flash promo 2026-09-10'a kadar; sonrası 0.12/0.24 ve
        # daha yükseğe döner — `OPENROUTER_MAX_SPEND_USD` bu tabloyu baz alır.
        "upstage/solar-pro4": {"in": 0.03, "out": 0.12},
        "inclusionai/ling-3.0-flash": {"in": 0.021, "out": 0.063},
        "deepseek/deepseek-v4-flash": {"in": 0.0679, "out": 0.168},
        "z-ai/glm-5.2": {"in": 0.3276, "out": 1.03},
        "deepseek/deepseek-v4-pro": {"in": 0.4679, "out": 0.9358},
        "google/gemini-3.7-flash": {"in": 0.75, "out": 3.75},
        # live_llm_gate.py varsayılan hakemi (OPENROUTER_JUDGE_MODEL). Guard bunu
        # fiyatsız görüp gate'i UNKNOWN_PRICING ile düşürüyordu — eklendi.
        "openai/gpt-5.6-sol-pro": {"in": 2.0, "out": 10.0}
    }
    
    TIER_1_MODEL = os.getenv("OPENROUTER_TIER_1_MODEL", MODEL_REGISTRY["solar_pro4"])
    TIER_2_MODEL = os.getenv("OPENROUTER_TIER_2_MODEL", MODEL_REGISTRY["ling_3_flash"])
    DEFAULT_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", MODEL_REGISTRY["gemini_3_7_flash"])

    CHAINS = {
        "depth": [MODEL_REGISTRY["solar_pro4"], MODEL_REGISTRY["glm_5_2"], MODEL_REGISTRY["deepseek_v4_pro"]],
        "vision": [MODEL_REGISTRY["gemini_3_7_flash"]],
        "dialogue": [MODEL_REGISTRY["solar_pro4"], MODEL_REGISTRY["deepseek_v4_flash"]],
        "fast": [MODEL_REGISTRY["ling_3_flash"], MODEL_REGISTRY["deepseek_v4_flash"]],
    }
    # Agent policies make specialist selection explicit while retaining a
    # bounded, capability-compatible failover chain.
    AGENT_CHAINS = {
        "cognitive_profiler": [MODEL_REGISTRY["solar_pro4"], MODEL_REGISTRY["deepseek_v4_pro"], MODEL_REGISTRY["glm_5_2"]],
        "friction_detector": [MODEL_REGISTRY["ling_3_flash"], MODEL_REGISTRY["deepseek_v4_flash"]],
        "passion_mapper": [MODEL_REGISTRY["deepseek_v4_pro"], MODEL_REGISTRY["solar_pro4"], MODEL_REGISTRY["glm_5_2"]],
        "resonance_synthesizer": [MODEL_REGISTRY["solar_pro4"], MODEL_REGISTRY["deepseek_v4_pro"]],
        "vision_analyzer": [MODEL_REGISTRY["gemini_3_7_flash"]],
        "autonomous_verifier": [MODEL_REGISTRY["deepseek_v4_flash"], MODEL_REGISTRY["ling_3_flash"]],
    }

    LOCAL_DEFAULT_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
    LOCAL_DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "dolphin-llama3:latest")

    def get_chain(self, task: str) -> List[str]:
        env_var = f"OPENROUTER_CHAIN_{task.upper()}"
        if os.getenv(env_var):
            return [m.strip() for m in os.getenv(env_var).split(",") if m.strip()]
        return self.CHAINS.get(task.lower(), [self.TIER_1_MODEL, self.TIER_2_MODEL])

    def get_agent_chain(self, agent_name: str | None, task: str) -> List[str]:
        if agent_name:
            env_var = f"OPENROUTER_AGENT_CHAIN_{agent_name.upper()}"
            if os.getenv(env_var):
                return [m.strip() for m in os.getenv(env_var).split(",") if m.strip()]
            if agent_name in self.AGENT_CHAINS:
                return self.AGENT_CHAINS[agent_name]
        return self.get_chain(task)

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.local_base_url = self.LOCAL_DEFAULT_URL
        self.local_model = self.LOCAL_DEFAULT_MODEL
        self.request_timeout_seconds = min(
            45.0,
            max(0.1, self._env_float("LLM_REQUEST_TIMEOUT_SECONDS", 45.0)),
        )
        self.use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        self.client = None
        self.local_client = None
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_opened_at = 0.0
        self.live_unlocked = False
        self.total_cost = 0.0
        # P2-MALİYET: kümülatif harcama ve sert üst limit
        self.spend_usd = 0.0
        self.spend_cap_usd = self._env_float("OPENROUTER_MAX_SPEND_USD", 0.0)
        self.max_output_tokens = max(1, int(self._env_float("OPENROUTER_MAX_OUTPUT_TOKENS", 4096)))
        self.image_token_reserve = max(0, int(self._env_float("OPENROUTER_IMAGE_TOKEN_RESERVE", 8192)))
        self._budget_lock = threading.Lock()
        self._reserved_spend_usd = 0.0
        self._budget_reservations: dict[str, float] = {}
        # [017]: PINEAL_ALLOW_UNPRICED_MODELS=1 ile yapılan takipsiz çağrı sayacı
        self.unpriced_calls = 0
        # Bounded diagnostic history. Agent evidence is populated from a
        # task-local LLMCallScope, never by slicing this shared list.
        self.call_log: List[dict[str, Any]] = []
        self._rebuild()
        self.cache = build_cache_from_env()

    @contextmanager
    def capture_calls(self, task_id: Optional[str], agent_id: Optional[str]) -> Iterator[LLMCallScope]:
        """Bind subsequent calls to a task/agent and collect their exact records."""
        scope = LLMCallScope(task_id=task_id, agent_id=agent_id)
        token = _active_call_scope.set(scope)
        try:
            yield scope
        finally:
            _active_call_scope.reset(token)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_call(
        self,
        kind: str,
        model: str,
        provider: str,
        *,
        call_id: Optional[str] = None,
        started_at: Optional[str] = None,
        cache_hit: bool = False,
        attempt: int = 0,
        duration_ms: int = 0,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        cost_usd: float = 0.0,
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        """Append one JSON-serializable record for a logical gateway call."""
        scope = _active_call_scope.get()
        finished_at = self._utc_now()
        record: dict[str, Any] = {
            "call_id": call_id or str(uuid.uuid4()),
            "task_id": scope.task_id if scope else None,
            "agent_id": scope.agent_id if scope else None,
            "kind": kind,
            "model": model,
            "provider": provider,
            "attempt": attempt,
            # Compatibility for existing telemetry consumers; ``attempt`` is
            # the canonical production contract field.
            "attempts": attempt,
            "cache_hit": cache_hit,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": float(cost_usd),
            "started_at": started_at or finished_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "error": error,
            # Compatibility alias retained while API/UI consumers migrate.
            "at": finished_at,
        }
        self.call_log.append(record)
        if len(self.call_log) > 500:
            del self.call_log[: len(self.call_log) - 500]
        if scope is not None:
            scope.records.append(record.copy())
        return record

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    def _usage_cost(self, model: str, usage: Any) -> float:
        """Return observed provider cost from token usage without mutating state."""
        import logging
        if usage is None:
            return 0.0
        rates = self.MODEL_PRICING.get(model)
        if rates is None:
            logging.warning("SPEND: fiyati bilinmeyen model, harcama takip edilemiyor: %s", model)
            return 0.0
        try:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
        return (
            prompt_tokens * rates["in"] + completion_tokens * rates["out"]
        ) / 1_000_000.0

    def _account_spend(self, model: str, usage: Any) -> float:
        """Account observed usage atomically (compatibility entry point)."""
        cost = self._usage_cost(model, usage)
        with self._budget_lock:
            self.spend_usd += cost
            self.total_cost += cost
        return cost

    def _maximum_call_cost(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        images: Optional[List[str]],
    ) -> float:
        """Conservative reservation based on bounded output and UTF-8 input bytes."""
        rates = self.MODEL_PRICING[model]
        # A tokenizer cannot consume more tokens than the encoded input bytes;
        # reserve extra message framing and a configurable image allowance.
        prompt_bytes = len(prompt.encode("utf-8")) + len((system_prompt or "").encode("utf-8"))
        prompt_tokens = prompt_bytes + 64 + self.image_token_reserve * len(images or [])
        return (
            prompt_tokens * rates["in"] + self.max_output_tokens * rates["out"]
        ) / 1_000_000.0

    def _reserve_budget(self, call_id: str, amount: float) -> None:
        """Atomically reserve worst-case cost before any paid provider call."""
        if self.spend_cap_usd <= 0:
            return
        with self._budget_lock:
            projected = self.spend_usd + self._reserved_spend_usd + amount
            if projected > self.spend_cap_usd:
                raise SpendCapExceeded(self._cap_message_locked(projected=projected))
            self._budget_reservations[call_id] = amount
            self._reserved_spend_usd += amount

    def _release_budget(self, call_id: str) -> None:
        """Release a reservation after failure, rejection, or cancellation."""
        with self._budget_lock:
            amount = self._budget_reservations.pop(call_id, 0.0)
            self._reserved_spend_usd = max(0.0, self._reserved_spend_usd - amount)

    def _settle_budget(self, call_id: str, model: str, usage: Any) -> float:
        """Replace a reservation with observed cost in one atomic operation."""
        cost = self._usage_cost(model, usage)
        with self._budget_lock:
            reserved = self._budget_reservations.pop(call_id, 0.0)
            self._reserved_spend_usd = max(0.0, self._reserved_spend_usd - reserved)
            self.spend_usd += cost
            self.total_cost += cost
        return cost

    def _cap_exceeded(self) -> bool:
        if self.spend_cap_usd <= 0:
            return False
        with self._budget_lock:
            return self.spend_usd + self._reserved_spend_usd >= self.spend_cap_usd

    def _cap_message_locked(self, *, projected: Optional[float] = None) -> str:
        committed = self.spend_usd
        reserved = self._reserved_spend_usd
        value = projected if projected is not None else committed + reserved
        return (
            f"OPENROUTER_SPEND_CAP_EXCEEDED: committed=${committed:.6f}, "
            f"reserved=${reserved:.6f}, projected=${value:.6f}, "
            f"cap=${self.spend_cap_usd:.6f} (OPENROUTER_MAX_SPEND_USD)."
        )

    def _cap_message(self) -> str:
        with self._budget_lock:
            return self._cap_message_locked()

    def budget_status(self) -> dict[str, float | int]:
        """Return an atomic telemetry snapshot of committed and reserved spend."""
        with self._budget_lock:
            return {
                "spend_usd": self.spend_usd,
                "reserved_usd": self._reserved_spend_usd,
                "cap_usd": self.spend_cap_usd,
                "active_reservations": len(self._budget_reservations),
            }

    def _pricing_guard(self, model: str, *, kind: str) -> None:
        """[017] fix: fiyatı bilinmeyen model için ÜCRETLİ canlı çağrı varsayılan
        olarak REDDEDİLİR. Eski davranış yalnızca uyarı loglayıp harcamayı 0
        sayıyordu; bu, bilinmeyen modelle spend cap'in sessiz bypass'ı demekti.

        Açık kabul: PINEAL_ALLOW_UNPRICED_MODELS=1 (takipsiz maliyet bilinçli
        seçimdir; unpriced_calls sayacı gözlemlenebilirlikte raporlanır).
        """
        if model in self.MODEL_PRICING:
            return
        if os.getenv("PINEAL_ALLOW_UNPRICED_MODELS", "0") == "1":
            self.unpriced_calls += 1
            import logging
            logging.warning(
                "SPEND: fiyatı bilinmeyen modele açıkça izin verildi "
                "(PINEAL_ALLOW_UNPRICED_MODELS=1): %s", model,
            )
            return
        msg = (
            f"UNKNOWN_PRICING: '{model}' için fiyat kaydı yok; harcama takip edilemez "
            "ve spend cap bypass edilemez. MODEL_PRICING'e fiyat ekleyin veya "
            "PINEAL_ALLOW_UNPRICED_MODELS=1 ile takipsiz maliyeti açıkça kabul edin."
        )
        raise RuntimeError(msg)

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """[018] fix: retry yalnızca GEÇİCİ hata sınıflarına uygulanır.

        Retryable:   timeout, bağlantı hatası/reset, 408, 429, 5xx
        Non-retryable: 400/401/403/404/422, geçersiz istek, model yok,
                     bağlam limiti, spend cap (ayrı ele alınır)
        Bilinmeyen durumlar mevcut davranışı (retry) korur.
        """
        try:
            from openai import APIConnectionError, APITimeoutError
            if isinstance(exc, (APITimeoutError, APIConnectionError)):
                return True
        except Exception:
            pass

        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            return status in (408, 429) or 500 <= status < 600

        err = str(exc).lower()
        if any(m in err for m in (
            "timeout", "timed out", "connection", "connect", "refused",
            "reset", "10061", "429", "rate limit", "rate_limit",
            "502", "503", "504", "internal server error",
        )):
            return True
        if any(m in err for m in (
            "400", "403", "404", "422", "invalid_request", "invalid request",
            "model_not_found", "context_length", "unauthorized", "invalid_api_key",
        )):
            return False
        return True

    def set_key(self, key: str, unlock_live: bool = False):
        self.api_key = key
        if unlock_live:
            self.live_unlocked = True
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_opened_at = 0.0
        self._rebuild()

    def set_local_config(self, base_url: str = None, model_name: str = None, active: bool = True):
        if base_url:
            self.local_base_url = base_url
        if model_name:
            self.local_model = model_name
        self.use_local = active
        self._rebuild()

    def _rebuild(self):
        if self.api_key:
            self.client = AsyncOpenAI(
                base_url=self.openrouter_base_url,
                api_key=self.api_key,
                max_retries=0,
            )
        # Local client (Ollama/LM Studio/vLLM)
        try:
            self.local_client = AsyncOpenAI(
                base_url=self.local_base_url,
                api_key="ollama",
                max_retries=0,
            )
        except Exception:
            self.local_client = None

    async def query(
        self,
        prompt: str,
        temperature: float = 0.7,
        tier: int = 1,
        model: str = None,
        system_prompt: str = None,
        images: Optional[List[str]] = None,
    ) -> str:
        """Execute one logical LLM call and emit exactly one call-id record.

        Retries retain the same ``call_id``. Task/agent ownership comes from
        ``capture_calls`` and is therefore isolated across concurrent asyncio
        tasks sharing this gateway.
        """
        import asyncio
        import logging

        call_id = str(uuid.uuid4())
        started_at = self._utc_now()
        t0 = time.monotonic()

        is_local_request = bool(
            (model and any(marker in model.lower() for marker in ("local", "ollama", "127.0.0.1")))
            or self.use_local
        )
        if is_local_request:
            selected_model = self.local_model if (not model or model == "local") else model
            provider = "local"
        else:
            selected_model = (
                os.getenv("OPENROUTER_VISION_MODEL", self.DEFAULT_VISION_MODEL)
                if images and not model
                else model or (self.TIER_1_MODEL if tier == 1 else self.TIER_2_MODEL)
            )
            provider = "openrouter"
        logical_cost_usd = 0.0

        def log_call(
            *,
            error: Optional[str] = None,
            attempt: int = 0,
            cache_hit: bool = False,
            prompt_tokens: Optional[int] = None,
            completion_tokens: Optional[int] = None,
            cost_usd: Optional[float] = None,
            record_provider: Optional[str] = None,
        ) -> dict[str, Any]:
            return self._log_call(
                "query",
                selected_model,
                record_provider or provider,
                call_id=call_id,
                started_at=started_at,
                cache_hit=cache_hit,
                attempt=attempt,
                duration_ms=int((time.monotonic() - t0) * 1000),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=logical_cost_usd if cost_usd is None else cost_usd,
                error=error,
            )

        if self.circuit_open:
            if time.time() - getattr(self, "circuit_opened_at", 0.0) > 60.0:
                self.circuit_open = False
                self.failure_count = 0
            else:
                log_call(error="CIRCUIT_OPEN", record_provider="circuit_breaker")
                raise RuntimeError("Circuit breaker ACIK - LLM servisi durduruldu (60s bekleme devrede)")

        if is_local_request:
            target_client = self.local_client or AsyncOpenAI(base_url=self.local_base_url, api_key="ollama")
        else:
            if os.getenv("LIVE_LLM_E2E") != "1" and not getattr(self, "live_unlocked", False):
                log_call(error="REAL_LLM_CALL_NOT_EXECUTED")
                raise RuntimeError(
                    "REAL_LLM_CALL_NOT_EXECUTED: Canlı LLM çağrıları kapalı. "
                    "Açmak için: (1) Kasa'ya API anahtarı girin (oturum boyunca açılır), veya "
                    "(2) .env dosyasına OPENROUTER_API_KEY yazıp LIVE_LLM_E2E=1 yapıp sunucuyu yeniden başlatın."
                )
            if not self.client:
                log_call(error="LLM_KEY_MISSING")
                raise RuntimeError(
                    "LLM anahtari yok. Vault veya .env ile OPENROUTER_API_KEY enjekte et veya Local LLM seç."
                )
            target_client = self.client

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if images:
            content = [{"type": "text", "text": prompt}]
            content += [{"type": "image_url", "image_url": {"url": url}} for url in images]
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        cache_key = None
        if (
            not images
            and not is_local_request
            and self.cache
            and self.cache.is_cachable(prompt, images)
        ):
            cache_key = self.cache.make_key(
                prompt=prompt,
                model=selected_model,
                system_prompt=system_prompt,
                temperature=temperature,
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                log_call(cache_hit=True, record_provider="cache")
                return cached

        budget_reserved = False
        if not is_local_request:
            try:
                self._pricing_guard(selected_model, kind="query")
            except RuntimeError:
                log_call(error="UNKNOWN_PRICING")
                raise
            if self.spend_cap_usd > 0:
                if selected_model not in self.MODEL_PRICING:
                    log_call(error="UNKNOWN_PRICING_FOR_SPEND_CAP")
                    raise RuntimeError(
                        "UNKNOWN_PRICING_FOR_SPEND_CAP: unpriced models cannot run while a spend cap is active"
                    )
                reservation = self._maximum_call_cost(selected_model, prompt, system_prompt, images)
                try:
                    self._reserve_budget(call_id, reservation)
                    budget_reserved = True
                except SpendCapExceeded:
                    log_call(error="OPENROUTER_SPEND_CAP_EXCEEDED")
                    raise

        max_retries = 3
        for attempt_index in range(max_retries):
            attempt = attempt_index + 1
            try:
                # A malformed but billed provider response may have settled the
                # previous reservation. Every subsequent paid attempt must
                # reserve again before another request can leave the process.
                if (
                    not is_local_request
                    and self.spend_cap_usd > 0
                    and not budget_reserved
                ):
                    reservation = self._maximum_call_cost(
                        selected_model, prompt, system_prompt, images
                    )
                    self._reserve_budget(call_id, reservation)
                    budget_reserved = True
                response = await target_client.chat.completions.create(
                    model=selected_model,
                    temperature=temperature,
                    messages=messages,
                    timeout=self.request_timeout_seconds,
                    max_tokens=self.max_output_tokens,
                )
                self.failure_count = 0
                usage = getattr(response, "usage", None)
                cost_usd = 0.0
                if not is_local_request:
                    # Settle observed provider usage before parsing the body.
                    # Otherwise a malformed paid response could be retried as
                    # though no billable request had occurred.
                    cost_usd = self._settle_budget(call_id, selected_model, usage)
                    logical_cost_usd += cost_usd
                    budget_reserved = False
                content = response.choices[0].message.content

                if cache_key and content:
                    try:
                        self.cache.put(cache_key, content)
                    except Exception as cache_error:
                        # A cache write must never retry an already billed call.
                        logging.warning("LLM response cache write failed: %s", cache_error)
                log_call(
                    attempt=attempt,
                    prompt_tokens=(
                        int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else None
                    ),
                    completion_tokens=(
                        int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else None
                    ),
                    cost_usd=logical_cost_usd,
                )
                return content
            except asyncio.CancelledError:
                if budget_reserved:
                    self._release_budget(call_id)
                    budget_reserved = False
                log_call(error="CANCELLED", attempt=attempt)
                raise
            except SpendCapExceeded:
                if budget_reserved:
                    self._release_budget(call_id)
                    budget_reserved = False
                log_call(error="OPENROUTER_SPEND_CAP_EXCEEDED", attempt=attempt)
                raise
            except Exception as exc:
                error_text = str(exc).lower()
                is_connection_error = any(
                    marker in error_text for marker in ("connection", "connect", "refused", "10061")
                )

                if is_local_request and is_connection_error:
                    if os.getenv("ALLOW_LOCAL_TO_CLOUD_FALLBACK", "false").lower() != "true":
                        log_call(error="LOCAL_PROVIDER_UNAVAILABLE", attempt=attempt)
                        raise RuntimeError(
                            "LOCAL_PROVIDER_UNAVAILABLE: Yerel model erişilemedi; "
                            "bulut fallback'i açıkça yetkilendirilmedi."
                        ) from exc
                    if self.client:
                        logging.warning(
                            "Yetkili provider fallback: local %s → cloud %s",
                            selected_model,
                            self.TIER_1_MODEL,
                        )
                        target_client = self.client
                        selected_model = self.TIER_1_MODEL
                        is_local_request = False
                        provider = "openrouter"
                        try:
                            self._pricing_guard(selected_model, kind="query")
                        except RuntimeError:
                            log_call(error="UNKNOWN_PRICING", attempt=attempt)
                            raise
                        if self.spend_cap_usd > 0:
                            reservation = self._maximum_call_cost(
                                selected_model, prompt, system_prompt, images
                            )
                            try:
                                self._reserve_budget(call_id, reservation)
                                budget_reserved = True
                            except SpendCapExceeded:
                                log_call(error="OPENROUTER_SPEND_CAP_EXCEEDED", attempt=attempt)
                                raise
                        continue

                is_auth_error = any(
                    marker in error_text for marker in ("401", "unauthorized", "invalid_api_key")
                )
                if is_auth_error:
                    if budget_reserved:
                        self._release_budget(call_id)
                        budget_reserved = False
                    logging.error("LLM Gateway authentication error: %s", exc)
                    log_call(error="AUTH_FAILED", attempt=attempt)
                    raise RuntimeError(f"LLM API Key rejected: {exc}") from exc

                if not self._is_retryable_error(exc):
                    if budget_reserved:
                        self._release_budget(call_id)
                        budget_reserved = False
                    logging.error("LLM Gateway non-retryable error (%s): %s", type(exc).__name__, exc)
                    log_call(error=f"NON_RETRYABLE::{type(exc).__name__}", attempt=attempt)
                    raise

                if attempt_index < max_retries - 1:
                    backoff = 2 ** attempt_index
                    logging.warning(
                        "LLM Bağlantı/Gecikme Hatası (deneme %s/%s), %ss içinde tekrar deneniyor... %s",
                        attempt,
                        max_retries,
                        backoff,
                        exc,
                    )
                    try:
                        await asyncio.sleep(backoff)
                    except asyncio.CancelledError:
                        if budget_reserved:
                            self._release_budget(call_id)
                            budget_reserved = False
                        log_call(error="CANCELLED", attempt=attempt)
                        raise
                    continue

                if budget_reserved:
                    self._release_budget(call_id)
                    budget_reserved = False
                self.failure_count += 1
                if self.failure_count > 5:
                    self.circuit_open = True
                    self.circuit_opened_at = time.time()
                log_call(error=type(exc).__name__, attempt=attempt)
                raise

    def extract_json(self, text: str) -> dict:
        """Markdown fence ve etiketleri temizleyip JSON ayıklar."""
        text = text.strip()
        
        # 1. Kod blokları varsa önce onları dene
        if "```json" in text:
            blocks = [b.split("```")[0].strip() for b in text.split("```json")[1:]]
            for b in reversed(blocks):
                try:
                    return json.loads(b)
                except Exception:
                    pass
        elif "```" in text:
            blocks = [b.split("```")[0].strip() for b in text.split("```")[1:]]
            for b in reversed(blocks):
                try:
                    return json.loads(b)
                except Exception:
                    pass

        # 2. Doğrudan parse dene
        try:
            return json.loads(text)
        except Exception:
            pass

        # 3. Metin içindeki tüm JSON nesnelerini tara
        decoder = json.JSONDecoder()
        start = 0
        found_objs = []
        while start < len(text):
            pos = text.find('{', start)
            if pos == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(text[pos:])
                if isinstance(obj, dict):
                    found_objs.append(obj)
                start = pos + max(1, end_idx)
            except Exception:
                start = pos + 1

        if found_objs:
            for obj in reversed(found_objs):
                if "$defs" not in obj and "properties" not in obj:
                    return obj
            return found_objs[-1]

        raise ValueError(f"JSON Ayrıştırma Hatası | Orijinal metin: {text[:100]}...")

    def _coerce_to_schema(self, parsed_data: Any, schema: Type[T]) -> T:
        if not isinstance(parsed_data, dict):
            raise ValueError(f"Beklenen JSON nesnesi (dict), alınan: {type(parsed_data)}")
        
        # Eğer model 'properties' altına sarmaladıysa unwrap yap
        if "properties" in parsed_data and hasattr(schema, "model_fields") and "properties" not in schema.model_fields:
            props = parsed_data["properties"]
            if isinstance(props, dict):
                sample_val = next(iter(props.values()), None)
                if not isinstance(sample_val, dict) or "type" not in sample_val:
                    parsed_data = props

        # Eğer model sınıf ismi altına sarmaladıysa unwrap yap
        root_key = getattr(schema, "__name__", "")
        if root_key and root_key in parsed_data and isinstance(parsed_data[root_key], dict):
            parsed_data = parsed_data[root_key]

        # Alan seviyesinde unwrap (LLM {field: {title: ..., default: ...}} dönerse)
        cleaned = dict(parsed_data)
        if hasattr(schema, "model_fields"):
            for field_name, field_info in schema.model_fields.items():
                if field_name in cleaned and isinstance(cleaned[field_name], dict):
                    inner = cleaned[field_name]
                    if "default" in inner:
                        cleaned[field_name] = inner["default"]
                    elif "value" in inner:
                        cleaned[field_name] = inner["value"]
                    elif "const" in inner:
                        cleaned[field_name] = inner["const"]
                    elif "description" in inner and len(inner) == 1:
                        cleaned[field_name] = inner["description"]
        parsed_data = cleaned

        return schema.model_validate(parsed_data)

    async def query_json(self, prompt: str, schema: Type[T], temperature: float = 0.7, tier: int = 1, model: str = None, images: Optional[List[str]] = None) -> T:
        """LLM'den sorgu atar, beklenen JSON formatını (Pydantic schema) tamir mekanizmasıyla garanti eder."""
        full_prompt = (
            f"{prompt}\n\n"
            f"Lütfen çıktını SADECE aşağıdaki JSON formatına uygun DOLDURULMUŞ JSON verisi olarak ver. Markdown etiketi kullanma, hiçbir ek açıklama yapma:\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        
        selected_model = model or (self.TIER_1_MODEL if tier == 1 else self.TIER_2_MODEL)
        response_text = ""
        try:
            response_text = await self.query(full_prompt, temperature, tier=tier, model=selected_model, images=images)
            parsed_data = self.extract_json(response_text)
            return self._coerce_to_schema(parsed_data, schema)
        except Exception as err:
            # 1 Kez Repair (Tamir) İsteği
            repair_prompt = (
                f"Önceki çıktın geçerli bir doldurulmuş JSON verisi değildi veya şemaya uymadı ({err}). "
                f"Lütfen SADECE şu şemaya uygun DOLDURULMUŞ veriyi JSON olarak döndür (şema etiketlerini değil, gerçek veriyi yaz):\n{json.dumps(schema.model_json_schema(), ensure_ascii=False)}\n"
                f"DİKKAT: Eksik veri varsa uydurma kelimeler veya sahte skorlar YAZMA. Sadece var olanları yerleştir.\n"
                f"Eklediğin bozuk çıktı şuydu:\n{response_text[:200]}"
            )
            repair_text = await self.query(repair_prompt, temperature, tier=tier, model=selected_model, images=images)
            parsed_data = self.extract_json(repair_text)
            return self._coerce_to_schema(parsed_data, schema)

    async def query_chain(
        self,
        prompt: str,
        task: str = "depth",
        temperature: float = 0.7,
        system_prompt: str = None,
        images: Optional[List[str]] = None
    ) -> str:
        """Görev bazlı model zincirini çalıştırır.

        429/5xx/timeout/hata durumunda zincirdeki sıradaki modele düşer.
        AUTH (401/unauthorized) hatası düşmez, anında yükseltilir.
        """
        import logging
        chain = self.get_chain(task)
        last_exception = None

        for model in chain:
            try:
                return await self.query(
                    prompt=prompt,
                    temperature=temperature,
                    model=model,
                    system_prompt=system_prompt,
                    images=images
                )
            except Exception as e:
                err_str = str(e).lower()
                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str
                if is_auth_error:
                    raise

                last_exception = e
                logging.warning(
                    f"Model zincirinde hata [{task} -> {model}]: {e}. Sıradaki modele geçiliyor..."
                )
                continue

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Zincirdeki tüm modeller tükendi ({task})")

    async def query_json_chain(
        self,
        prompt: str,
        schema: Type[T],
        task: str = "depth",
        temperature: float = 0.7,
        images: Optional[List[str]] = None,
        agent_name: Optional[str] = None,
    ) -> T:
        """Görev bazlı model zinciri ile şemalı JSON sorgusu yapar.

        429/5xx/timeout/şema hatalarında zincirdeki sıradaki modele düşer.
        AUTH (401/unauthorized) hatası düşmez, anında yükseltilir.
        """
        import logging
        chain = self.get_agent_chain(agent_name, task)
        last_exception = None

        for model in chain:
            try:
                return await self.query_json(
                    prompt=prompt,
                    schema=schema,
                    temperature=temperature,
                    model=model,
                    images=images
                )
            except Exception as e:
                err_str = str(e).lower()
                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str
                if is_auth_error:
                    raise

                last_exception = e
                logging.warning(
                    f"JSON Model zincirinde hata [{task} -> {model}]: {e}. Sıradaki modele geçiliyor..."
                )
                continue

        if last_exception:
            raise last_exception
        raise RuntimeError(f"JSON Zincirindeki tüm modeller tükendi ({task})")
