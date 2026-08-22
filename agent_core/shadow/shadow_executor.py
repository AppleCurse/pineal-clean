import asyncio
from typing import Dict, Any, List
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
        # 1. Dark Triad Analizi
        dark = self.dark_triad.analyze(task_input['target_profile'])
        strategy = self.dark_triad.generate_strategy(dark)
        
        # 2. Mirror (Kullanıcı analizi)
        # MirrorOfTruth expects `execute(input_data: Dict, memory)`
        # But wait! MirrorOfTruth needs LLMGateway in its newer signature. Actually MirrorOfTruth only needed LLMGateway in some versions, or maybe it instantiates its own.
        # Wait, in PinealExecutor `self.agents["mirror_truth"].execute` is called without LLM? No, wait, PinealExecutor calls:
        # await self.agents["mirror_truth"].execute({"target_behavior": human_result, ...}, memory, self.llm_gateway)
        
        mirror_result = await self.mirror.execute(
            {
                "user_rituals": task_input.get('user_profile', {}).get('rituals', []),
                "user_music": task_input.get('user_profile', {}).get('music', ''),
                "user_envies": task_input.get('user_profile', {}).get('envies', '')
            }, 
            None, # No memory used for now
            self.llm_gateway
        )
        
        # 3. NLP Sequence
        nlp_seq = self.dark_nlp.generate_sequence(
            task_input['target_profile'],
            task_input.get('desired_action', 'cevap ver')
        )
        
        # 4. Presupposition Chain
        beliefs = task_input.get('target_beliefs', ['anlaşılmak', 'özel hissetmek'])
        presup_chain = self.presupposition.generate_chain(beliefs)
        
        # 5. Pattern Interrupt
        pattern_input = {
            'target_analysis': {
                'surface_identity': task_input['target_profile'].get('bio', '')[:50],
                'detected_wound': strategy['vector'],
                'resonance_potential': dark.exploitability
            },
            'user_mirror': mirror_result.model_dump() if hasattr(mirror_result, 'model_dump') else mirror_result,
            'sacred_rules': ""
        }
        pattern_result = await self.pattern.execute(pattern_input, None, self.llm_gateway)
        
        # 6. Birleştir
        final_message = self._synthesize(
            pattern_result.message, 
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
