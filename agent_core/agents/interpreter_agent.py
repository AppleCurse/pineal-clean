from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, List, Optional
import asyncio
import os

class CodeExecutionChunk(BaseModel):
    type: str  # "code", "output", "error", "message"
    format: str  # "python", "shell", "text"
    content: str

class InterpreterResult(BaseModel):
    prompt: str
    code_blocks: List[str] = []
    output: str = ""
    status: str = "success"  # "success", "error", "halted"
    error_message: Optional[str] = None
    
    model_config = ConfigDict(extra="forbid")

class InterpreterAgent:
    """
    Pineal-Heretic Tactical Code Interpreter Agent.
    Runs Open Interpreter to programmatically generate and execute Python/Shell code.
    """
    def __init__(self, llm_gateway=None):
        self.llm_gateway = llm_gateway

    def _setup_interpreter(self, api_key: str = None, model: str = None, auto_run: bool = True):
        try:
            from interpreter import interpreter
            
            interpreter.auto_run = auto_run
            interpreter.offline = False
            
            # Key configuration
            key = api_key or (self.llm_gateway.api_key if self.llm_gateway else os.getenv("OPENROUTER_API_KEY"))
            if key and not key.startswith("sk-or-v1-YOUR"):
                interpreter.llm.api_key = key
                interpreter.llm.api_base = "https://openrouter.ai/api/v1"
                selected_model = model or "meta-llama/llama-3.3-70b-instruct"
                if not selected_model.startswith("openrouter/") and not ("local" in selected_model.lower() or "ollama" in selected_model.lower()):
                    selected_model = f"openrouter/{selected_model}"
                interpreter.llm.model = selected_model
            
            return interpreter
        except ImportError as e:
            import logging
            logging.error(f"InterpreterAgent setup failed: {e}. 'open-interpreter' is likely not installed.")
            return None

    async def execute_task(self, prompt: str, api_key: str = None, model: str = None, auto_run: bool = True) -> InterpreterResult:
        """
        Executes a task prompt using Open Interpreter and returns structured execution results.
        """
        interpreter = self._setup_interpreter(api_key=api_key, model=model, auto_run=auto_run)
        
        if interpreter is None:
            # Fallback when open-interpreter package is not available
            return InterpreterResult(
                prompt=prompt,
                code_blocks=[],
                output="Open Interpreter kütüphanesi aktif değil.",
                status="error",
                error_message="open-interpreter package not installed"
            )
            
        try:
            # Run open-interpreter programmatically via asyncio thread pool
            def _run():
                messages = interpreter.chat(prompt, display=False)
                output_text = ""
                code_list = []
                for msg in messages:
                    if msg.get("type") == "code":
                        code_list.append(msg.get("code", ""))
                    if msg.get("type") == "output":
                        output_text += msg.get("output", "") + "\n"
                    elif msg.get("content"):
                        output_text += str(msg.get("content")) + "\n"
                return code_list, output_text.strip()

            code_blocks, output = await asyncio.to_thread(_run)
            return InterpreterResult(
                prompt=prompt,
                code_blocks=code_blocks,
                output=output or "İşlem tamamlandı.",
                status="success"
            )
        except Exception as e:
            return InterpreterResult(
                prompt=prompt,
                code_blocks=[],
                output="",
                status="error",
                error_message=str(e)
            )

    async def execute(self, input_data: Dict[str, Any], memory=None, llm_gateway=None) -> InterpreterResult:
        """PinealExecutor standart ajan arayüzü"""
        prompt = input_data.get("prompt") or input_data.get("task", "Sistem durumunu kontrol et.")
        gw = llm_gateway or self.llm_gateway
        key = gw.api_key if gw else None
        return await self.execute_task(prompt=prompt, api_key=key)
