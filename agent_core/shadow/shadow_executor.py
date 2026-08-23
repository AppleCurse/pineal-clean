from typing import Dict
from pydantic import BaseModel, ConfigDict

# Import yeni modüller
from agent_core.nlp.dark_nlp import EmbeddedCommandEngine, PresuppositionEngine
from agent_core.psychology.dark_triad import DarkTriadAnalyzer
from agent_core.agents.pattern_interrupt import PatternInterrupt
from agent_core.agents.mirror_truth import MirrorOfTruth
from agent_core.services.llm_gateway import LLMGateway

class ShadowResult(BaseModel):
    message: str
    dark_profile: Dict
    strategy: str
    nlp_sequence: list
    confidence: float
    
    model_config = ConfigDict(extra="forbid")

class ShadowExecutor:
    def __init__(self):
        self.dark_nlp = EmbeddedCommandEngine()
        self.presupposition = PresuppositionEngine()
        self.dark_triad = DarkTriadAnalyzer()
        self.pattern = PatternInterrupt()
        self.mirror = MirrorOfTruth()
        self.llm_gateway = LLMGateway()
    
    async def execute(self, task_input: Dict) -> ShadowResult:
        import logging
        log = logging.getLogger(__name__)

        # 1. Dark Triad Analizi (LLM gerektirmez — deterministik)
        dark = self.dark_triad.analyze(task_input.get('target_profile', {}))
        strategy = self.dark_triad.generate_strategy(dark)

        # 2. Mirror (LLM gerektirir — fallback ile korumalı)
        mirror_result = None
        try:
            mirror_result = await self.mirror.execute(
                {
                    "user_rituals": task_input.get('user_profile', {}).get('rituals', []),
                    "user_music": task_input.get('user_profile', {}).get('music', ''),
                    "user_envies": task_input.get('user_profile', {}).get('envies', '')
                },
                None,
                self.llm_gateway
            )
        except Exception as e:
            log.warning("ShadowExecutor: Mirror LLM atlandı: %s", e)

        # 3. NLP Sequence (LLM gerektirmez — deterministik)
        nlp_seq = self.dark_nlp.generate_sequence(
            task_input.get('target_profile', {}),
            task_input.get('desired_action', 'cevap ver')
        )

        # 4. Presupposition Chain (LLM gerektirmez — deterministik)
        beliefs = task_input.get('target_beliefs', ['anlaşılmak', 'özel hissetmek'])
        presup_chain = self.presupposition.generate_chain(beliefs)

        # 5. Pattern Interrupt (LLM gerektirir — fallback ile korumalı)
        pattern_message = strategy.get('vector', 'Analiz tamamlandı')
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
