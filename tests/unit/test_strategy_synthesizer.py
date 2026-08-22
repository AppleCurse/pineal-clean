import pytest
from unittest.mock import MagicMock
from agent_core.aspasia.strategy_synthesizer import StrategySynthesizer, MessageStrategy

class MockProfile:
    def __init__(self, wound, attachment_val, exploitability_val):
        self.core_wound = wound
        self.attachment = MagicMock()
        self.attachment.value = attachment_val
        self.exploitability = exploitability_val

def test_synthesize_abandonment_anxious():
    synth = StrategySynthesizer()
    profile = MockProfile('abandonment', 'anxious', 0.8)
    
    # Run the real logic
    strategy = synth.synthesize(profile, achilles=None, user_profile=None)
    
    assert isinstance(strategy, MessageStrategy)
    assert strategy.line_2 == "O an yaln\u0131z kald\u0131\u011f\u0131n\u0131 hissetti\u011fin, ama kimseye s\u00f6yleyemedi\u011fin..."
    assert strategy.line_3 == "Buraday\u0131m. Gitmeyece\u011fim."
    assert strategy.compliance_probability == 80.0
    assert "Yaln\u0131zl\u0131k" in strategy.hook or "Sensizlik" in strategy.hook

def test_synthesize_shame_avoidant():
    synth = StrategySynthesizer()
    profile = MockProfile('shame', 'avoidant', 0.5)
    
    strategy = synth.synthesize(profile, achilles=None, user_profile=None)
    
    assert isinstance(strategy, MessageStrategy)
    assert strategy.line_2 == "G\u00f6r\u00fcnenden daha derin oldu\u011funu biliyorum."
    assert strategy.line_3 == "Sana alan veriyorum. Bask\u0131 yok."
    assert strategy.compliance_probability == 50.0

def test_synthesize_betrayal_secure():
    synth = StrategySynthesizer()
    profile = MockProfile('betrayal', 'secure', 0.9)
    
    strategy = synth.synthesize(profile, achilles=None, user_profile=None)
    
    assert isinstance(strategy, MessageStrategy)
    assert strategy.line_2 == "G\u00fcvenmek zor. \u00d6zellikle ge\u00e7mi\u015fte ya\u015fananlardan sonra."
    assert strategy.line_3 == "Seninle ayn\u0131 frekanstay\u0131m."
    assert strategy.compliance_probability == 90.0

def test_synthesize_fallback_default():
    synth = StrategySynthesizer()
    profile = MockProfile('unknown_wound', 'unknown_attachment', 0.3)
    
    # Should fallback to abandonment/secure
    strategy = synth.synthesize(profile, achilles=None, user_profile=None)
    assert strategy.line_2 == "O an yaln\u0131z kald\u0131\u011f\u0131n\u0131 hissetti\u011fin, ama kimseye s\u00f6yleyemedi\u011fin..."
    assert strategy.line_3 == "Seninle ayn\u0131 frekanstay\u0131m."
    assert strategy.compliance_probability == 30.0
