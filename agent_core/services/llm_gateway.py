import os
import json
import re
import os
import json
import re
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Type, TypeVar, Any

T = TypeVar('T', bound=BaseModel)

class LLMGateway:
    TIER_1_MODEL = "meta-llama/llama-3.3-70b-instruct" # Yüksek IQ (Karanlık Triad, Karşı-hamle)
    TIER_2_MODEL = "meta-llama/llama-3.1-8b-instruct" # Hızlı/Ucuz (Basit veri işleme)

    LOCAL_DEFAULT_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
    LOCAL_DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "dolphin-llama3:latest")

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.local_base_url = self.LOCAL_DEFAULT_URL
        self.local_model = self.LOCAL_DEFAULT_MODEL
        self.use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        self.client = None
        self.local_client = None
        self.failure_count = 0
        self.circuit_open = False
        self._rebuild()

    def set_key(self, key: str):
        self.api_key = key
        self.failure_count = 0
        self.circuit_open = False
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

    async def query(self, prompt: str, temperature: float = 0.7, tier: int = 1, model: str = None, system_prompt: str = None) -> str:
        if self.circuit_open:
            raise RuntimeError("Circuit breaker ACIK - LLM servisi durduruldu")
        
        # Eğer local model seçildiyse veya global use_local aktifse
        is_local_request = (model and ("local" in model.lower() or "ollama" in model.lower() or "127.0.0.1" in model.lower())) or self.use_local
        
        if is_local_request:
            target_client = self.local_client or AsyncOpenAI(base_url=self.local_base_url, api_key="ollama")
            selected_model = self.local_model if (not model or model == "local") else model
        else:
            import os
            if os.getenv("LIVE_LLM_E2E") != "1":
                raise RuntimeError("REAL_LLM_CALL_NOT_EXECUTED: LIVE_LLM_E2E=1 flag is missing. External API calls are blocked.")
            
            if not self.client:
                raise RuntimeError("LLM anahtari yok. Vault veya .env ile OPENROUTER_API_KEY enjekte et veya Local LLM seç.")
            target_client = self.client
            selected_model = model or (self.TIER_1_MODEL if tier == 1 else self.TIER_2_MODEL)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
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
                is_rate_limit = "429" in err_str or "rate" in err_str or "too many requests" in err_str
                is_auth_error = "401" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str
                
                if is_auth_error:
                    logging.error(f"LLM Gateway authentication error: {e}")
                    raise RuntimeError(f"LLM API Key rejected: {e}") from e
                    
                self.failure_count += 1
                if self.failure_count > 5:
                    self.circuit_open = True
                    
                if is_rate_limit and attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    logging.warning(f"LLM Rate limit (attempt {attempt+1}/{max_retries}), retrying in {backoff}s... {e}")
                    await asyncio.sleep(backoff)
                    continue
                
                # If not rate limited or out of retries, raise
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

        return schema(**parsed_data)

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
