import os
import json
import time
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Type, TypeVar, Any, Optional, List

T = TypeVar('T', bound=BaseModel)

class LLMGateway:
    TIER_1_MODEL = os.getenv("OPENROUTER_TIER_1_MODEL", "anthropic/claude-sonnet-4.5") # SOTA Bilişsel Zeka, Psikolojik Derinlik & Rezonans (Claude)
    TIER_2_MODEL = "deepseek/deepseek-chat" # Hızlı & Yüksek IQ
    DEFAULT_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "google/gemini-3.7-flash") # SOTA Çoklu Modlu Görsel Zeka

    CHAINS = {
        "depth": ["anthropic/claude-sonnet-5", "anthropic/claude-sonnet-4.5", "meta-llama/llama-3.3-70b-instruct"],
        "vision": ["anthropic/claude-sonnet-5", "google/gemini-3.7-flash", "meta-llama/llama-3.2-90b-vision-instruct"],
        "dialogue": ["anthropic/claude-sonnet-4.5", "anthropic/claude-sonnet-5", "meta-llama/llama-3.3-70b-instruct"],
        "fast": ["deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"],
    }

    LOCAL_DEFAULT_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
    LOCAL_DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "dolphin-llama3:latest")

    def get_chain(self, task: str) -> List[str]:
        env_var = f"OPENROUTER_CHAIN_{task.upper()}"
        if os.getenv(env_var):
            return [m.strip() for m in os.getenv(env_var).split(",") if m.strip()]
        return self.CHAINS.get(task.lower(), [self.TIER_1_MODEL, self.TIER_2_MODEL])

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
        self._rebuild()

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
                raise RuntimeError("Circuit breaker ACIK - LLM servisi durduruldu (60s bekleme devrede)")
        
        # Eğer local model seçildiyse veya global use_local aktifse
        is_local_request = (model and ("local" in model.lower() or "ollama" in model.lower() or "127.0.0.1" in model.lower())) or self.use_local
        
        if is_local_request:
            target_client = self.local_client or AsyncOpenAI(base_url=self.local_base_url, api_key="ollama")
            selected_model = self.local_model if (not model or model == "local") else model
        else:
            import os
            if os.getenv("LIVE_LLM_E2E") != "1" and not getattr(self, "live_unlocked", False):
                raise RuntimeError(
                    "REAL_LLM_CALL_NOT_EXECUTED: Canlı LLM çağrıları kapalı. "
                    "Açmak için: (1) Kasa'ya API anahtarı girin (oturum boyunca açılır), veya "
                    "(2) .env dosyasına OPENROUTER_API_KEY yazıp LIVE_LLM_E2E=1 yapıp sunucuyu yeniden başlatın."
                )
            
            if not self.client:
                raise RuntimeError("LLM anahtari yok. Vault veya .env ile OPENROUTER_API_KEY enjekte et veya Local LLM seç.")
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

        import asyncio
        import logging
        max_retries = 3

        for attempt in range(max_retries):
            try:
                r = await target_client.chat.completions.create(
                    model=selected_model, temperature=temperature,
                    messages=messages,
                    timeout=45.0
                )
                self.failure_count = 0
                return r.choices[0].message.content
            except Exception as e:
                err_str = str(e).lower()
                is_conn_error = "connection" in err_str or "connect" in err_str or "refused" in err_str or "10061" in err_str
                
                # Eğer yerel LLM (Ollama) bağlantısı koptuysa ve OpenRouter anahtarımız varsa otomatik buluta geç
                if is_local_request and is_conn_error and self.client:
                    logging.warning(f"Yerel model ({selected_model}) bağlantısı kurulamadı. OpenRouter bulut modeline ({self.TIER_1_MODEL}) geçiliyor...")
                    target_client = self.client
                    selected_model = self.TIER_1_MODEL
                    is_local_request = False
                    continue

                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str
                if is_auth_error:
                    logging.error(f"LLM Gateway authentication error: {e}")
                    raise RuntimeError(f"LLM API Key rejected: {e}") from e
                    
                if attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    logging.warning(f"LLM Bağlantı/Gecikme Hatası (deneme {attempt+1}/{max_retries}), {backoff}s içinde tekrar deneniyor... {e}")
                    await asyncio.sleep(backoff)
                    continue
                
                self.failure_count += 1
                if self.failure_count > 5:
                    self.circuit_open = True
                    self.circuit_opened_at = time.time()
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

    async def query_json(self, prompt: str, schema: Type[T], temperature: float = 0.7, tier: int = 1, model: str = None) -> T:
        """LLM'den sorgu atar, beklenen JSON formatını (Pydantic schema) tamir mekanizmasıyla garanti eder."""
        full_prompt = (
            f"{prompt}\n\n"
            f"Lütfen çıktını SADECE aşağıdaki JSON formatına uygun DOLDURULMUŞ JSON verisi olarak ver. Markdown etiketi kullanma, hiçbir ek açıklama yapma:\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        
        selected_model = model or (self.TIER_1_MODEL if tier == 1 else self.TIER_2_MODEL)
        response_text = ""
        try:
            response_text = await self.query(full_prompt, temperature, tier=tier, model=selected_model)
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
            repair_text = await self.query(repair_prompt, temperature, tier=tier, model=selected_model)
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
        temperature: float = 0.7
    ) -> T:
        """Görev bazlı model zinciri ile şemalı JSON sorgusu yapar.

        429/5xx/timeout/şema hatalarında zincirdeki sıradaki modele düşer.
        AUTH (401/unauthorized) hatası düşmez, anında yükseltilir.
        """
        import logging
        chain = self.get_chain(task)
        last_exception = None

        for model in chain:
            try:
                return await self.query_json(
                    prompt=prompt,
                    schema=schema,
                    temperature=temperature,
                    model=model
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
