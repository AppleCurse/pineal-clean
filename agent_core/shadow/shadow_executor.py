from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict

# Import yeni modüller
from agent_core.nlp.dark_nlp import EmbeddedCommandEngine, PresuppositionEngine
from agent_core.psychology.dark_triad import DarkTriadAnalyzer, DarkTriadProfile
from agent_core.agents.pattern_interrupt import PatternInterrupt
from agent_core.agents.mirror_truth import MirrorOfTruth
from agent_core.services.llm_gateway import LLMGateway

class ShadowResult(BaseModel):
    message: str
    dark_profile: Dict
    strategy: str
    nlp_sequence: list
    confidence: float
    data_confidence: bool = True          # False → LLM kullanılamadı, NLP deterministik
    fallback_reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

class ShadowExecutor:
    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        # [030] fix: gateway enjekte edilebilir. PinealExecutor kendi (anahtarlı)
        # gateway'ini verir; yetimsiz ikinci gateway production'da LLM katmanlarını
        # yapısal olarak hep fallback'e düşürüyordu.
        self.dark_nlp = EmbeddedCommandEngine()
        self.presupposition = PresuppositionEngine()
        self.dark_triad = DarkTriadAnalyzer()
        self.pattern = PatternInterrupt()
        self.llm_gateway = llm_gateway or LLMGateway()
        self.mirror = MirrorOfTruth(self.llm_gateway)

    @staticmethod
    def _has_target_evidence(task_input: Dict) -> bool:
        """Hedef üzerinde gerçek analiz girdisi var mı?

        [019] kapısı: hedef bio/posts/username/name/images yoksa shadow
        stratejisi ve mesajı ÜRETİLEMEZ; sıfır veriden 'empathy' şablonu
        sahte kanıt olur.
        """
        target = task_input.get("target_profile", {})
        if not isinstance(target, dict):
            target = {}
        return bool(
            target.get("bio") or target.get("posts")
            or target.get("username") or target.get("name")
            or target.get("images")
        )

    async def execute(self, task_input: Dict) -> ShadowResult:
        import logging
        log = logging.getLogger(__name__)

        if not self._has_target_evidence(task_input):
            log.warning(
                "ShadowExecutor: hedef kanıtı yok; shadow profili üretilmedi "
                "(sahte strateji/mesaj yasak)."
            )
            return ShadowResult(
                message="",
                dark_profile=DarkTriadProfile().model_dump(),
                strategy="unavailable",
                nlp_sequence=[],
                confidence=0.0,
                data_confidence=False,
                fallback_reason="target_evidence_unavailable",
            )

        # 1. Dark Triad Analizi (LLM gerektirmez — deterministik)
        dark = self.dark_triad.analyze(task_input.get('target_profile', {}))
        strategy = self.dark_triad.generate_strategy(dark)

        # [024 devamı] Gözlemlenebilir markör yoksa strateji ÜRETİLMEZ;
        # kısmi markör eşiği geçmediyse de strateji türetilmez. Sahte
        # "empathy" etiketi ve şablon mesaj bu durumda yasaktır.
        if strategy["vector"] == "unavailable":
            return ShadowResult(
                message="",
                dark_profile=dark.model_dump(),
                strategy="unavailable",
                nlp_sequence=[],
                confidence=0.0,
                data_confidence=False,
                fallback_reason="dark_triad_markers_unobserved",
            )
        if strategy["vector"] == "unobserved":
            return ShadowResult(
                message="",
                dark_profile=dark.model_dump(),
                strategy="unavailable",
                nlp_sequence=[],
                confidence=0.0,
                data_confidence=False,
                fallback_reason="strategy_unobserved",
            )

        # 2. Mirror (LLM gerektirir — fallback ile korumalı)
        # [031] fix: payload sözleşmesindeki gerçek alan adlarını kullan
        # (private_rituals/late_night_playlist/secret_envies + user_context).
        # Eski 'rituals/music/envies' anahtarları hiçbir üretici tarafından
        # yazılmıyordu; kullanıcı verisi mirror'a hiç ulaşmıyordu.
        mirror_result = None
        try:
            mirror_result = await self.mirror.execute(
                {
                    "user_profile": task_input.get("user_profile", {}),
                    "user_context": task_input.get("user_context", {}),
                }
            )
        except Exception as e:
            log.warning("ShadowExecutor: Mirror LLM atlandı: %s", e)

        # 3. NLP Sequence (LLM gerektirmez — deterministik)
        # Kullanıcı istem vermediyse varsayılan eylem ÜRETİLMEZ (eski
        # 'cevap ver' default'u sahte istemdi).
        desired_action = task_input.get('desired_action')
        nlp_seq = self.dark_nlp.generate_sequence(
            task_input.get('target_profile', {}),
            desired_action if isinstance(desired_action, str) else ''
        )

        # 4. Presupposition Chain (LLM gerektirmez — deterministik)
        # Kullanıcı inanç listesi vermediyse boş; sahte varsayılan inanç
        # ('anlaşılmak', 'özel hissetmek') artık enjekte edilmez.
        beliefs = task_input.get('target_beliefs') or []
        presup_chain = self.presupposition.generate_chain(beliefs)

        # 5. Pattern Interrupt (LLM gerektirir — fallback ile korumalı)
        pattern_message = strategy.get('vector') or "unavailable"
        try:
            pattern_input = {
                'target_analysis': {
                    'surface_identity': task_input.get('target_profile', {}).get('bio', '')[:50],
                    'detected_wound': strategy['vector'],
                    'resonance_potential': dark.exploitability
                },
                'user_mirror': mirror_result.model_dump() if mirror_result and hasattr(mirror_result, 'model_dump') else {},
                'sacred_rules': ""
            }
            pattern_result = await self.pattern.execute(pattern_input, None, self.llm_gateway)
            pattern_message = pattern_result.message
        except Exception as e:
            log.warning("ShadowExecutor: Pattern LLM atlandı: %s", e)

        # 6. Birleştir
        final_message = self._synthesize(
            pattern_message,
            nlp_seq,
            presup_chain,
            strategy
        )

        return ShadowResult(
            message=final_message,
            dark_profile=dark.model_dump(),
            strategy=strategy['vector'],
            nlp_sequence=nlp_seq,
            confidence=dark.exploitability
        )
    
    def _synthesize(self, base_msg: str, nlp_seq: list, presup: list, strategy: Dict) -> str:
        """Tüm katmanları birleştir"""
        presup_intro = presup[0]['sentence'] if presup else ""
        nlp_command = nlp_seq[1]['text'] if len(nlp_seq) > 1 else ""
        
        return f"{presup_intro} {base_msg} {nlp_command}"
