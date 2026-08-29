import os
import json
import time
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Type, TypeVar, Any, Optional, List

from agent_core.services.response_cache import build_cache_from_env

T = TypeVar('T', bound=BaseModel)


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
        "upstage/solar-pro4": {"in": 0.03, "out": 0.12},
        "inclusionai/ling-3.0-flash": {"in": 0.021, "out": 0.063},
        "deepseek/deepseek-v4-flash": {"in": 0.14, "out": 0.28},
        "z-ai/glm-5.2": {"in": 0.10, "out": 0.10},
        "deepseek/deepseek-v4-pro": {"in": 0.50, "out": 1.00},
        "google/gemini-3.7-flash": {"in": 0.375, "out": 1.875}
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
        self.local_base_url = self.LOCAL_DEFAULT_URL
        self.local_model = self.LOCAL_DEFAULT_MODEL
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
        # [017]: PINEAL_ALLOW_UNPRICED_MODELS=1 ile yapılan takipsiz çağrı sayacı
        self.unpriced_calls = 0
        # Gözlemlenebilirlik: her LLM çağrısının model/provider/deneme
        # kaydı. Evidence chain'e ajan bazında yazılır (task_executor).
        self.call_log: List[dict] = []
        # P2-9 PROVENANCE: son başarılı çağrının modeli. Executor bunu
        # AgentRun.output_summary["_provenance"] içine damgalar; UI bu
        # damga olmadan "gerçek LLM çıktısı" rozeti gösteremez.
        self.last_call_meta: dict = {}
        self._rebuild()
        self.cache = build_cache_from_env()

    def _log_call(
        self,
        kind: str,
        model: str,
        provider: str,
        *,
        cache_hit: bool = False,
        attempts: int = 0,
        duration_ms: int = 0,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append an auditable record of a single LLM interaction."""
        self.call_log.append({
            "kind": kind,
            "model": model,
            "provider": provider,
            "cache_hit": cache_hit,
            "attempts": attempts,
            "duration_ms": duration_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "error": error,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        # Sınırsız büyümesin; kanıt zinciri zaten slice ile alır.
        if len(self.call_log) > 500:
            del self.call_log[: len(self.call_log) - 500]

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    def _account_spend(self, model: str, usage: Any) -> None:
        """P2-MALİYET: yanıt usage'ından tahmini harcamayı işler.
        Fiyatı bilinmeyen modellerde uyarı loglanır, harcama işlenmez.
        """
        import logging
        if usage is None:
            return
        rates = self.MODEL_PRICING.get(model)
        if rates is None:
            logging.warning("SPEND: fiyati bilinmeyen model, harcama takip edilemiyor: %s", model)
            return
        try:
            p_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            c_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        except (TypeError, ValueError):
            return
        cost = (p_tokens * rates["in"] + c_tokens * rates["out"]) / 1_000_000.0
        self.spend_usd += cost
        self.total_cost += cost  # geriye uyumluluk

    def _cap_exceeded(self) -> bool:
        return self.spend_cap_usd > 0 and self.spend_usd >= self.spend_cap_usd

    def _cap_message(self) -> str:
        return (
            f"OPENROUTER_SPEND_CAP_EXCEEDED: tahmini harcama ${self.spend_usd:.4f} "
            f">= ust limit ${self.spend_cap_usd:.2f} (OPENROUTER_MAX_SPEND_USD). "
            f"Daha fazla canli LLM cagrisi yapilmadi."
        )

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
        self._log_call(kind, model, "openrouter", error="UNKNOWN_PRICING")
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
            self.client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
        # Local client (Ollama/LM Studio/vLLM)
        try:
            self.local_client = AsyncOpenAI(base_url=self.local_base_url, api_key="ollama")
        except Exception:
            self.local_client = None

    async def query(self, prompt: str, temperature: float = 0.7, tier: int = 1, model: str = None, system_prompt: str = None, images: Optional[List[str]] = None) -> str:
        """Metin (ve opsiyonel data-URL görseller) sorgusu.

        images verilirse (ve model açıkça belirtilmemişse) vision destekli
        varsayılan modele geçilir; içerik multimodal content dizisi olarak gönderilir.
        """
        if self.circuit_open:
            if time.time() - getattr(self, "circuit_opened_at", 0.0) > 60.0:
                self.circuit_open = False
                self.failure_count = 0
            else:
                self._log_call("query", getattr(self, "local_model", "") or "?",
                               "circuit_breaker", error="CIRCUIT_OPEN")
                raise RuntimeError("Circuit breaker ACIK - LLM servisi durduruldu (60s bekleme devrede)")
        
        # Eğer local model seçildiyse veya global use_local aktifse
        is_local_request = (model and ("local" in model.lower() or "ollama" in model.lower() or "127.0.0.1" in model.lower())) or self.use_local

        # P2-MALİYET: bütçe aşıldıysa canlı çağrı hiç yapılmaz
        if not is_local_request and self._cap_exceeded():
            self._log_call("query", model or "?", "openrouter", error=self._cap_message())
            raise SpendCapExceeded(self._cap_message())
        
        if is_local_request:
            target_client = self.local_client or AsyncOpenAI(base_url=self.local_base_url, api_key="ollama")
            selected_model = self.local_model if (not model or model == "local") else model
        else:
            import os
            if os.getenv("LIVE_LLM_E2E") != "1" and not getattr(self, "live_unlocked", False):
                msg = (
                    "REAL_LLM_CALL_NOT_EXECUTED: Canlı LLM çağrıları kapalı. "
                    "Açmak için: (1) Kasa'ya API anahtarı girin (oturum boyunca açılır), veya "
                    "(2) .env dosyasına OPENROUTER_API_KEY yazıp LIVE_LLM_E2E=1 yapıp sunucuyu yeniden başlatın."
                )
                self._log_call("query", model or "?", "openrouter", error="REAL_LLM_CALL_NOT_EXECUTED")
                raise RuntimeError(msg)
            
            if not self.client:
                msg = "LLM anahtari yok. Vault veya .env ile OPENROUTER_API_KEY enjekte et veya Local LLM seç."
                self._log_call("query", model or "?", "openrouter", error="LLM_KEY_MISSING")
                raise RuntimeError(msg)
            target_client = self.client
            if images and not model:
                # FAZ 3: görsel varsa vision modeline geç (env ile ezilebilir)
                selected_model = os.getenv("OPENROUTER_VISION_MODEL", self.DEFAULT_VISION_MODEL)
            else:
                selected_model = model or (self.TIER_1_MODEL if tier == 1 else self.TIER_2_MODEL)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if images:
            # OpenAI-uyumlu multimodal content
            content = [{"type": "text", "text": prompt}]
            content += [{"type": "image_url", "image_url": {"url": u}} for u in images]
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        # --- Birebir yanit onbellegi (salt-metin, yerel/vision disi) ---
        # Anahtar model+system_prompt+sicaklik+prompt'u icerir; farkli
        # model/kisilik yanitlari asla birbirine karismaz.
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
                self._log_call("query", selected_model, "cache", cache_hit=True)
                self.last_call_meta = {"model": selected_model, "cached": True, "provider": "cache"}
                return cached

        # [017] fix: ücretli çağrı öncesi fiyat guard'ı. Cache hit ücretsizdir;
        # guard yalnızca gerçek provider çağrısından önce uygulanır. Local
        # istekler ücretsizdir, muaf tutulur.
        if not is_local_request:
            self._pricing_guard(selected_model, kind="query")

        import asyncio
        import logging
        max_retries = 3

        t0 = time.time()
        for attempt in range(max_retries):
            try:
                # P2-MALİYET: döngü içinde de cap kontrolü
                if not is_local_request and self._cap_exceeded():
                    raise SpendCapExceeded(self._cap_message())
                r = await target_client.chat.completions.create(
                    model=selected_model, temperature=temperature,
                    messages=messages,
                    timeout=45.0
                )
                self.failure_count = 0

                # P2-MALİYET: token harcama hesabı
                if not is_local_request:
                    self._account_spend(selected_model, getattr(r, "usage", None))

                usage = getattr(r, "usage", None)
                content = r.choices[0].message.content
                if cache_key and content:
                    self.cache.put(cache_key, content)
                self.last_call_meta = {
                    "model": selected_model,
                    "cached": False,
                    "provider": "local" if is_local_request else "openrouter",
                }
                self._log_call(
                    "query", selected_model,
                    "local" if is_local_request else "openrouter",
                    attempts=attempt + 1,
                    duration_ms=int((time.time() - t0) * 1000),
                    prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0)
                        if usage is not None else None,
                    completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0)
                        if usage is not None else None,
                )
                return content
            except SpendCapExceeded:
                raise
            except Exception as e:
                err_str = str(e).lower()
                is_conn_error = "connection" in err_str or "connect" in err_str or "refused" in err_str or "10061" in err_str
                
                # Provider boundary is explicit: local requests do not silently
                # become paid cloud requests. Opt-in is required for any switch.
                if is_local_request and is_conn_error:
                    if os.getenv("ALLOW_LOCAL_TO_CLOUD_FALLBACK", "false").lower() != "true":
                        raise RuntimeError(
                            "LOCAL_PROVIDER_UNAVAILABLE: Yerel model erişilemedi; "
                            "bulut fallback'i açıkça yetkilendirilmedi."
                        ) from e
                    if self.client:
                        logging.warning(f"Yetkili provider fallback: local {selected_model} → cloud {self.TIER_1_MODEL}")
                        target_client = self.client
                        selected_model = self.TIER_1_MODEL
                        is_local_request = False
                        continue

                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str
                if is_auth_error:
                    logging.error(f"LLM Gateway authentication error: {e}")
                    self._log_call("query", selected_model,
                                   "local" if is_local_request else "openrouter",
                                   attempts=attempt + 1,
                                   duration_ms=int((time.time() - t0) * 1000),
                                   error="AUTH_FAILED")
                    raise RuntimeError(f"LLM API Key rejected: {e}") from e

                # [018] fix: geçici OLMAYAN hata sınıfları (400/403/404/422,
                # geçersiz istek, model yok, bağlam limiti) retry EDİLMEZ.
                # Eskiden her generic Exception backoff'la 3 kez deneniyordu.
                if not self._is_retryable_error(e):
                    logging.error(f"LLM Gateway non-retryable error ({type(e).__name__}): {e}")
                    self._log_call("query", selected_model,
                                   "local" if is_local_request else "openrouter",
                                   attempts=attempt + 1,
                                   duration_ms=int((time.time() - t0) * 1000),
                                   error=f"NON_RETRYABLE::{type(e).__name__}")
                    raise

                if attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    logging.warning(f"LLM Bağlantı/Gecikme Hatası (deneme {attempt+1}/{max_retries}), {backoff}s içinde tekrar deneniyor... {e}")
                    await asyncio.sleep(backoff)
                    continue
                
                self.failure_count += 1
                if self.failure_count > 5:
                    self.circuit_open = True
                    self.circuit_opened_at = time.time()
                self._log_call("query", selected_model,
                               "local" if is_local_request else "openrouter",
                               attempts=attempt + 1,
                               duration_ms=int((time.time() - t0) * 1000),
                               error=type(e).__name__)
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
