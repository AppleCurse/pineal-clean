import json
from typing import List, Dict, Optional
from pydantic import BaseModel
from agent_core.services.llm_gateway import LLMGateway

class DialogueContext(BaseModel):
    task_id: str
    target_profile: dict
    user_profile: dict
    history: List[Dict[str, str]] = [] # [{"role": "target", "content": "..."}]

class DialogueResponse(BaseModel):
    stance: str  # "Agresif", "Savunmaci", "Ilgili", "Bilinmiyor"
    internal_analysis: str
    next_move: str

class DialogueManager:
    def __init__(self, llm_gateway: LLMGateway = None):
        self.llm = llm_gateway or LLMGateway()
        # In-memory storage for active sessions
        self.sessions: Dict[str, DialogueContext] = {}

    def start_session(self, task_id: str, target_profile: dict, user_profile: dict):
        self.sessions[task_id] = DialogueContext(
            task_id=task_id,
            target_profile=target_profile,
            user_profile=user_profile,
            history=[]
        )

    def add_message(self, task_id: str, role: str, content: str):
        if task_id in self.sessions:
            self.sessions[task_id].history.append({"role": role, "content": content})

    async def generate_response(self, task_id: str, target_message: str) -> DialogueResponse:
        if task_id not in self.sessions:
            raise ValueError("Oturum bulunamadı veya süresi doldu.")
            
        ctx = self.sessions[task_id]
        
        # Add target message to history
        self.add_message(task_id, "target", target_message)
        
        # Build prompt
        history_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in ctx.history])
        
        prompt = f"""
SEN BİR DİJİTAL PSİKOLOJİK HARP VE SOSYAL MÜHENDİSLİK YAPAY ZEKASISIN (PINEAL-HERETIC v3.0).
Hedefle bir konuşma içerisindesin. Aşağıda hedefin profili, senin kuralların ve şu ana kadarki diyalog geçmişi var.

HEDEF PROFİLİ:
{json.dumps(ctx.target_profile, ensure_ascii=False, indent=2)}

BİZİM PROFİLİMİZ / KUTSAL KURALLAR:
{json.dumps(ctx.user_profile, ensure_ascii=False, indent=2)}

DİYALOG GEÇMİŞİ:
{history_str}

GÖREV:
Hedefin son mesajını analiz et. Hedefin duruşunu (stance: Agresif, Savunmaci, Ilgili) belirle.
Sonrasında hedefin bu reaksiyonuna karşı, Kutsal Kuralları (örn: asla açıklama yapma, zayıflık gösterme, manipülatif ve gizemli kal) ihlal etmeyen, hedefin zayıflığını kullanacak bir 'next_move' (karşı-hamle/mesaj) üret.

YANIT FORMATI (Kati suretle JSON dön):
{{
    "stance": "Agresif",
    "internal_analysis": "Hedef neden bu tepkiyi verdi ve zafiyeti nerede?",
    "next_move": "Hedefe gönderilecek yeni manipülatif mesaj (direkt metin, tırnaksız, hazır)."
}}
"""
        response = await self.llm.query_json(prompt, DialogueResponse)
        
        # Add our response to history
        self.add_message(task_id, "agent", response.next_move)
        
        return response
