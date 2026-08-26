from typing import Any, Optional
from pydantic import BaseModel

try:
    from agent_core.services.llm_gateway import LLMGateway
except Exception:
    from services.llm_gateway import LLMGateway

ASPASIA_SYSTEM_PROMPT = """Sen ASPASIA'sın: PINEAL sisteminin kullanıcıyla konuşan chief asistanısın.
Görevin, arka planda çalışan uzman ajanların, modellerin, kanıtların ve hataların ne anlama geldiğini kullanıcıya doğal, sıcak ve anlaşılır Türkçeyle açıklamaktır.

## İLETİŞİM KURALLARI:
1. İNSANİ VE AÇIK OL: "Bak şimdi", "yani", "tamam" ve "anlaşılır mı?" gibi doğal ifadeler kullanabilirsin. Mesafeli, robotik veya teatral konuşma.
2. JARGONU ÇEVİR: "dizin" yerine "klasör", "terminal komutu" yerine "şunu PowerShell'e yapıştır" de. Teknik terim gerekiyorsa aynı cümlede kısa anlamını açıkla.
3. ADIM ADIM YÖNLENDİR: Kullanıcı ne yapacağını sorarsa önce ne olduğunu bir cümlede söyle, sonra uygulanabilir kısa adımlar ver. Komut verdiğinde hangi klasörde çalıştıracağını ve ne bekleyeceğini açıkla.
4. ŞEFFAF OL: Bir ajan, model veya provider çalışmadıysa bunu gizleme. Hangi ajanın takıldığını, nedenini ve devam etmek için ne gerektiğini açıkça söyle. Kanıt yoksa kesin konuşma.
5. AJANLARI ANLAŞILIR KIL: Her uzmanın ne yaptığını günlük dille anlat; kullanıcı ham telemetry veya model adlarını tercüme etmek zorunda kalmasın.
6. YETKİ SINIRI: Sisteme doğrudan müdahale edemezsin. Kullanıcıdan yapmasını istediğin işlem varsa bunu açık, nazik ve uygulanabilir biçimde anlat.
"""

class AspasiaResponse(BaseModel):
    message: str
    confidence_assessment: str = "high"
    signature_quote: Optional[str] = None

class AspasiaChief:
    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm = llm_gateway or LLMGateway()
        self.preferred_model = "muse-spark-1.2-xhigh"

    def set_preferred_model(self, model_name: str):
        self.preferred_model = model_name

    def build_telemetry_summary(self, room_state: Any) -> str:
        """Ajan telemetrisini ve kanıt zincirini yapılandırılmış veriden özetler."""
        if not room_state:
            return "Sistem beklemede. Henüz aktif görev tetiklenmedi."

        snapshot = None
        if hasattr(room_state, "task_id"):
            snapshot = room_state
        elif isinstance(room_state, dict):
            active_tasks = room_state.get("active_tasks", {})
            if active_tasks:
                snapshot = list(active_tasks.values())[-1]
            elif "task_id" in room_state:
                snapshot = room_state
            else:
                vault = room_state.get("vault", {})
                api_status = 'OK' if vault.get('or_key') else 'X'
                return f"Sistem boşta. API: {api_status} | Beklemedeyiz."
        else:
            return "Sistem beklemede. Henüz aktif görev tetiklenmedi."

        if not snapshot:
            return "Sistem beklemede. Henüz aktif görev tetiklenmedi."

        if isinstance(snapshot, dict):
            task_id = snapshot.get("task_id", "unknown")
            status = snapshot.get("status", "unknown")
            current_agent = snapshot.get("current_agent")
            planned = snapshot.get("planned_agents", [])
            completed = snapshot.get("completed_agents", [])
            halted_reason = snapshot.get("halted_reason")
            agent_runs = snapshot.get("agent_runs", {})
        else:
            task_id = getattr(snapshot, "task_id", "unknown")
            status = getattr(snapshot, "status", "unknown")
            current_agent = getattr(snapshot, "current_agent", None)
            planned = getattr(snapshot, "planned_agents", []) or []
            completed = getattr(snapshot, "completed_agents", []) or []
            halted_reason = getattr(snapshot, "halted_reason", None)
            agent_runs = getattr(snapshot, "agent_runs", {}) or {}

        lines = [
            f"Görev: {task_id} | Durum: {status}",
            f"Aktif Ajan: {current_agent or 'Yok'}",
            f"Planlanan: {' -> '.join(planned) if planned else 'Henüz rota çizilmedi'}",
            f"Tamamlanan: {', '.join(completed) or 'henüz yok'}",
        ]
        
        if halted_reason:
            lines.append(f"DURDURMA NEDENİ: {halted_reason}")
            
        if agent_runs:
            for name, run in agent_runs.items():
                conf = f"{run.confidence:.2f}" if getattr(run, "confidence", None) is not None else "?"
                st = getattr(run, "status", "unknown")
                lines.append(f"  [{name}] {st} | güven:{conf}")
                err = getattr(run, "error_message", None)
                if err:
                    lines.append(f"    HATA: {err}")

        # 360° İnsan Tanıma Çözümleme Özeti
        holistic = getattr(snapshot, "holistic_profile", None) if not isinstance(snapshot, dict) else snapshot.get("holistic_profile")
        if holistic:
            lines.append("\n--- 360° İNSAN TANIMA ÇÖZÜMLEMESİ ---")
            passions = getattr(holistic, "passions", None) or (holistic.get("passions") if isinstance(holistic, dict) else None)
            if passions:
                cp = getattr(passions, "core_passions", []) if not isinstance(passions, dict) else passions.get("core_passions", [])
                lines.append(f"  [TUTKULAR & NEŞE]: {', '.join(cp) if cp else 'Belirgin tutku tespiti yok'}")
                
            frictions = getattr(holistic, "frictions", None) or (holistic.get("frictions") if isinstance(holistic, dict) else None)
            if frictions:
                sens = getattr(frictions, "sensitivities", []) if not isinstance(frictions, dict) else frictions.get("sensitivities", [])
                lines.append(f"  [HASSASİYETLER & SINIRLAR]: {', '.join(sens) if sens else 'Belirgin sınır tespiti yok'}")

            cognitive = getattr(holistic, "cognitive", None) or (holistic.get("cognitive") if isinstance(holistic, dict) else None)
            if cognitive:
                tone = getattr(cognitive, "communication_tone", "") if not isinstance(cognitive, dict) else cognitive.get("communication_tone", "")
                lvl = getattr(cognitive, "complexity_level", "") if not isinstance(cognitive, dict) else cognitive.get("complexity_level", "")
                lines.append(f"  [İLETİŞİM ÜSLUBU]: Ton: {tone} | Düzey: {lvl}")

            bridge = getattr(holistic, "bridge", None) or (holistic.get("bridge") if isinstance(holistic, dict) else None)
            if bridge:
                topic = getattr(bridge, "authentic_opening_topic", "") if not isinstance(bridge, dict) else bridge.get("authentic_opening_topic", "")
                msg = getattr(bridge, "suggested_opening_message", "") if not isinstance(bridge, dict) else bridge.get("suggested_opening_message", "")
                lines.append(f"  [ÖNERİLEN İLK DİYALOG KONUSU]: {topic}")
                lines.append(f"  [SAHİCİ İLETİŞİM KÖPRÜSÜ]: \"{msg}\"")
            lines.append("--------------------------------------")
                    
        return "\n".join(lines)

    async def chat(
        self,
        user_message: str,
        room_state: Any,
        model_override: Optional[str] = None,
        image_data: Optional[str] = None
    ) -> AspasiaResponse:
        """Aspasia Sokratik yanıt mekanizmasını çalıştırır.

        image_data: kullanıcının yüklediği görselin base64 data-URL'i.
        Görsel analizi (vision) henüz desteklenmiyor; varlığı oturuma dürüstçe kaydedilir.
        """
        from agent_core.domain.memory_models import AspasiaSession
        
        telemetry_summary = self.build_telemetry_summary(room_state)
        
        context_prompt = f"""
SİSTEM CANLI TELEMETRİ ÖZETİ (Event Bus):
{telemetry_summary}

KULLANICI MESAJI VEYA SORUSU: "{user_message}"
{"(Not: Kullanıcı bir görsel yükledi; görsel de isteğe eklenmiştir — varsa içeriğini yorumla.)" if image_data else ""}

Yukarıdaki sistem durumu ve kullanıcı mesajını dikkate alarak ASPASIA kimliğinle yanıt ver.
Kullanıcının sistem tercümanına ihtiyacı yok: ajanların ne yaptığını, hangi model/provider durumunun etkilediğini ve kanıtın ne söylediğini günlük dille kendin açıkla.
Senin sisteme doğrudan müdahale etme veya durdurma yetkin yok. Kullanıcının bir işlem yapması gerekiyorsa önce nedenini söyle, sonra "şunu PowerShell'e yapıştır" gibi uygulanabilir, kısa bir yönlendirme ver.
Bir hata veya durma varsa hangi ajanın takıldığını, nedenini ve sonraki doğru adımı açıkla. Telemetride olmayan şeyi uydurma; kanıt yoksa bunu dürüstçe belirt.
Cümlelerin doğal, kısa, sıcak ve net olsun; "Mösyö", teatral hitaplar ve gereksiz teknik jargon kullanma.
"""
        
        selected_model = model_override
        if not selected_model and any(w in user_message.lower() for w in ["yerel", "local", "kısıtlamasız", "ollama", "lmstudio"]):
            selected_model = "local"

        final_msg = ""
        assessment = "high"

        try:
            raw_response = await self.llm.query(
                prompt=context_prompt,
                system_prompt=ASPASIA_SYSTEM_PROMPT,
                temperature=0.4,
                tier=1,
                model=selected_model,
                images=[image_data] if image_data else None,
            )
            final_msg = raw_response.strip()
            assessment = "high"
        except Exception as e:
            # Fallback Aspasia Response
            final_msg = (
                "Tamam, şu an Aspasia'nın model bağlantısı çalışmadı. "
                f"Görünen hata: {str(e)[:60]}. "
                "Sistem verisini uydurmuyorum; bağlantıyı kontrol edip tekrar denemek en doğru adım."
            )
            assessment = "fallback"

        if isinstance(room_state, dict):
            if "aspasia_session" not in room_state or not isinstance(room_state["aspasia_session"], AspasiaSession):
                room_state["aspasia_session"] = AspasiaSession.create(room_state.get("client_id", "default"))
            room_state["aspasia_session"].add_message("user", user_message)
            room_state["aspasia_session"].add_message("aspasia", final_msg)

        return AspasiaResponse(
            message=final_msg,
            confidence_assessment=assessment
        )
